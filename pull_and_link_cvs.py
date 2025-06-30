#!/usr/bin/env python3
import os
import sys
import logging
import tempfile
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np # For pd.NA handling

# --- Google Cloud Libraries ---
import google.auth
from google.cloud import storage, secretmanager
from google.cloud.sql.connector import Connector

# --- Database Libraries ---
import sqlalchemy
import pg8000.dbapi
from sqlalchemy import text # For raw SQL queries
from sqlalchemy.dialects import postgresql # For ON CONFLICT support if needed, but using direct execute

# --- Configuration Constants ---
GCS_BUCKET_NAME = "recruitment-engine-cvs-sp-260625"
GCS_CV_DIR = "candidate-cvs/" # Directory for CVs within the bucket

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Google Cloud Clients ---
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient() 

# Global connector instance for efficiency
connector = Connector() 

# --- File Type Mapping (Common CV formats) ---
# Map Content-Type headers to file extensions
CONTENT_TYPE_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    # Add more as needed
}

# --- Project and Secrets ---
def get_project_id():
    """Resolve GCP project from ADC."""
    try:
        _, project_id = google.auth.default()
        if not project_id:
            raise RuntimeError("Could not determine GCP Project ID")
        return project_id
    except Exception as e:
        logger.error(f"Could not determine GCP Project ID: {e}")
        raise

GCP_PROJECT_ID = get_project_id()

def get_secret(secret_id: str) -> str:
    """Fetch secret from Secret Manager."""
    name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        payload = secret_client.access_secret_version(request={"name": name}).payload.data
        return payload.decode("utf-8").strip()
    except Exception as e:
        logger.error(f"Failed to access secret '{secret_id}': {e}. Ensure service account has Secret Manager Secret Accessor role and secret exists with a version.")
        raise

def load_config() -> Dict[str, str]:
    """
    Load configuration from environment variables and Secret Manager.
    """
    logger.info("Loading configuration…")
    
    cfg = {}

    cfg["HIRE_USERNAME"] = os.getenv("HIRE_USERNAME", "").strip()
    logger.info(f"Loaded HIRE_USERNAME: '{cfg['HIRE_USERNAME']}'")

    try:
        cfg["HIRE_PASSWORD"] = get_secret("hire-password")
        logger.info("Successfully loaded HIRE_PASSWORD from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading HIRE_PASSWORD secret: {e}")
        raise

    try:
        cfg["DB_USER"] = get_secret("db-user")
        logger.info("Successfully loaded DB_USER from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading DB_USER secret: {e}")
        raise

    try:
        cfg["DB_PASS"] = get_secret("db-password")
        logger.info("Successfully loaded DB_PASS from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading DB_PASS secret: {e}")
        raise

    try:
        cfg["DB_NAME"] = get_secret("db-name")
        logger.info("Successfully loaded DB_NAME from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading DB_NAME secret: {e}")
        raise
    
    cfg["DB_CONNECTION_NAME"] = os.getenv("DB_CONNECTION_NAME", "").strip()
    logger.info(f"Loaded DB_CONNECTION_NAME from environment variable: '{cfg['DB_CONNECTION_NAME']}'")

    # New: Load DATES variable for date range of candidates to process
    cfg["DATES"] = os.getenv("DATES", "").strip()
    logger.info(f"Loaded DATES from environment variable: '{cfg['DATES']}'")

    if not all([cfg["HIRE_USERNAME"], cfg["HIRE_PASSWORD"], cfg["DB_USER"], 
                cfg["DB_PASS"], cfg["DB_NAME"], cfg["DB_CONNECTION_NAME"], cfg["DATES"]]):
        missing_keys = [k for k, v in cfg.items() if not v]
        logger.error(f"Missing required configuration values. Check environment variables and Secret Manager. Missing: {missing_keys}")
        raise ValueError("Missing required configuration values for ETL job.")
        
    logger.info("All essential configuration loaded successfully.")
    return cfg

# --- DB Setup ---
def get_db_engine(cfg: Dict[str, str]):
    """Creates a SQLAlchemy engine for connecting to Cloud SQL using the Cloud SQL Python Connector."""
    logger.info(f"Attempting to create connection engine for Cloud SQL instance: {cfg['DB_CONNECTION_NAME']}, database: {cfg['DB_NAME']}")
    try:
        def getconn():
            return connector.connect(
                cfg["DB_CONNECTION_NAME"],
                driver="pg8000",
                user=cfg["DB_USER"],
                password=cfg["DB_PASS"],
                db=cfg["DB_NAME"],
            )

        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_size=5,
            max_overflow=2,
            pool_timeout=30,
            pool_recycle=1800,
        )
        logger.info("Database engine created successfully.")
        return engine
    except Exception as e:
        logger.error(f"Failed to create database connection engine: {e}", exc_info=True)
        raise

# --- GCS Upload ---
def upload_cv_to_gcs(bucket_name: str, cv_data: bytes, dest_path: str, content_type: str = 'application/pdf'):
    """Uploads CV data (bytes) to GCS."""
    blob = storage_client.bucket(bucket_name).blob(dest_path)
    logger.info(f"Uploading CV to gs://{bucket_name}/{dest_path} with content type {content_type}")
    blob.upload_from_string(cv_data, content_type=content_type) # Use upload_from_string with content_type for binary
    logger.info(f"Successfully uploaded CV to gs://{bucket_name}/{dest_path}")
    return f"gs://{bucket_name}/{dest_path}"

# --- API Interaction for CVs ---
def get_api_auth_token(cfg: Dict[str, str]) -> Optional[str]:
    """Authenticates with Hire Intelligence API and returns access token."""
    auth_url = "https://partnersapi.applygateway.com/api/Login/login"
    auth_payload = {"Username": cfg["HIRE_USERNAME"], "Password": cfg["HIRE_PASSWORD"]}
    common_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://clients.hireintelligence.io",
        "Content-Type": "application/json"
    }
    auth_request_headers = {**common_headers, "Referer": "https://clients.hireintelligence.io/login"}

    try:
        logger.info(f"Authenticating user {cfg['HIRE_USERNAME']} via API for CV download...")
        response = requests.post(auth_url, json=auth_payload, headers=auth_request_headers, timeout=30)
        response.raise_for_status()
        auth_data = response.json()
        token = auth_data.get("data", {}).get("accessToken")
        if not token:
            logger.error(f"API login failed for CV download: missing accessToken. Response: {auth_data}")
            return None
        logger.info("🎉 API authentication successful for CV download.")
        return token
    except requests.exceptions.RequestException as e:
        logger.error(f"API authentication failed for CV download: {e}", exc_info=True)
        if e.response is not None:
            logger.error(f"Error Response Body: {e.response.text}")
        return None

def download_cv_from_api(cv_id: int, token: str) -> Optional[Dict]:
    """Downloads a single CV from the API."""
    cv_url = f"https://partnersapi.applygateway.com/api/Candidate/DownloadCV?cvid={cv_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "*/*", # Accept all content types for CVs
    }

    try:
        logger.info(f"Attempting to download CV for cVid: {cv_id}")
        response = requests.get(cv_url, headers=headers, timeout=60) # Increased timeout for large CVs
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        content_type = response.headers.get("Content-Type", "application/octet-stream").split(';')[0]
        file_extension = CONTENT_TYPE_TO_EXTENSION.get(content_type, ".bin") # Default to .bin if unknown
        
        logger.info(f"Successfully downloaded CV for cVid {cv_id}. Content-Type: {content_type}, Extension: {file_extension}")
        return {"data": response.content, "content_type": content_type, "extension": file_extension}
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else 'N/A'
        logger.warning(f"Failed to download CV for cVid {cv_id}. Status: {status_code}. Error: {e}")
        if e.response is not None:
            logger.warning(f"CV Download Error Response Body: {e.response.text[:200]}...") # Log partial body
        return None
    except Exception as e:
        logger.error(f"Unexpected error during CV download for cVid {cv_id}: {e}", exc_info=True)
        return None

# --- Main Logic for CV Pulling ---
def main():
    db_engine = None
    try:
        cfg = load_config()
        db_engine = get_db_engine(cfg)
        
        auth_token = get_api_auth_token(cfg)
        if not auth_token:
            logger.error("❌ Failed to get API authentication token. Cannot download CVs. Exiting.")
            sys.exit(1)

        # --- Dynamic Date Range based on DATES variable ---
        dates_var = cfg.get("DATES")
        start_date_obj = None
        end_date_obj = None

        if dates_var and dates_var.startswith("Week") and len(dates_var) > 4:
            try:
                week_num = int(dates_var[4:-4])
                year = int(dates_var[-4:])
                start_date_obj = datetime.fromisocalendar(year, week_num, 1).replace(tzinfo=timezone.utc)
                end_date_obj = datetime.fromisocalendar(year, week_num, 7).replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
                
                if end_date_obj > datetime.now(timezone.utc):
                    end_date_obj = datetime.now(timezone.utc)
                
                logger.info(f"Processing CVs for Week {week_num} of {year}: {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}")

            except ValueError as ve:
                logger.error(f"Invalid DATES format '{dates_var}'. Expected 'WeekXYear' (e.g., 'Week12024'). Exiting. Error: {ve}")
                sys.exit(1)
        else:
            logger.error(f"DATES variable '{dates_var}' not in 'WeekXYear' format or not provided. Exiting.")
            sys.exit(1)
        
        # --- Query Candidates for CV Download ---
        # Select candidates who have a cVid but no cv_gcs_path or a failed download status
        # We also filter by created_on date range
        query_sql = text(f"""
            SELECT
                id, email, job_ref_number, created_on, cv_id, first_name, last_name
            FROM
                candidates_daily_report
            WHERE
                cv_id IS NOT NULL
                AND (cv_gcs_path IS NULL OR cv_download_status LIKE 'Failed%')
                AND created_on >= :start_date
                AND created_on <= :end_date
            ORDER BY created_on ASC;
        """)

        candidates_to_process = []
        try:
            with db_engine.connect() as conn:
                result = conn.execute(query_sql, {
                    "start_date": start_date_obj,
                    "end_date": end_date_obj
                })
                for row in result:
                    candidates_to_process.append(row._asdict()) # Convert Row to dictionary
            logger.info(f"Found {len(candidates_to_process)} candidates with CVs to process for the period.")
        except Exception as e:
            logger.error(f"❌ Failed to query candidates from database: {e}", exc_info=True)
            sys.exit(1)

        if not candidates_to_process:
            logger.info("✅ No candidates found needing CV download for this period. Exiting successfully.")
            sys.exit(0)

        # --- Process Each Candidate's CV ---
        processed_count = 0
        download_success_count = 0
        download_fail_count = 0

        for candidate_record in candidates_to_process:
            candidate_id = candidate_record['id'] # Primary key of the candidate record
            cv_id = candidate_record['cv_id']
            first_name = candidate_record['first_name'] or "Unknown"
            last_name = candidate_record['last_name'] or "Candidate"
            job_ref_number = candidate_record['job_ref_number'] or "NoJobRef"
            created_on = candidate_record['created_on'] # Datetime object

            cv_gcs_path = None
            cv_download_status = None

            if cv_id is None:
                cv_download_status = "No CV ID"
                logger.info(f"Candidate {candidate_id} has no cVid. Status: {cv_download_status}")
            else:
                cv_data_result = download_cv_from_api(cv_id, auth_token)
                
                if cv_data_result:
                    try:
                        download_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                        # Filename: {job_ref_number}-{firstName}-{lastName}-{cVid}-{timestamp}.{ext}
                        filename = f"{job_ref_number}-{first_name}-{last_name}-{cv_id}-{download_timestamp}{cv_data_result['extension']}"
                        dest_path = f"{GCS_CV_DIR}{filename}"
                        
                        cv_gcs_path = upload_cv_to_gcs(GCS_BUCKET_NAME, cv_data_result['data'], dest_path, cv_data_result['content_type'])
                        cv_download_status = "Downloaded"
                        download_success_count += 1
                    except Exception as e:
                        cv_download_status = "Failed: GCS Upload Error"
                        logger.error(f"❌ Failed to upload CV for cVid {cv_id} to GCS: {e}", exc_info=True)
                        download_fail_count += 1
                else:
                    cv_download_status = "Failed: API Download" # Already logged in download_cv_from_api
                    download_fail_count += 1
            
            # --- Update Database Record ---
            update_sql = text(f"""
                UPDATE candidates_daily_report
                SET
                    cv_gcs_path = :cv_gcs_path,
                    cv_download_status = :cv_download_status
                WHERE
                    id = :candidate_id;
            """)
            try:
                with db_engine.connect() as conn:
                    conn.execute(update_sql, {
                        "cv_gcs_path": cv_gcs_path,
                        "cv_download_status": cv_download_status,
                        "candidate_id": candidate_id
                    })
                    conn.commit()
                logger.info(f"Updated DB for candidate {candidate_id} (cVid: {cv_id}). Status: {cv_download_status}")
            except Exception as e:
                logger.error(f"❌ Failed to update DB for candidate {candidate_id} (cVid: {cv_id}): {e}", exc_info=True)
                # This error should not halt the entire job, but it's critical to log.

            processed_count += 1
            time.sleep(1) # Small delay between CV downloads to be gentle on API

        logger.info(f"CV processing completed. Total candidates processed: {processed_count}. Successful downloads: {download_success_count}. Failed downloads: {download_fail_count}.")
        logger.info("✅ All CV tasks completed successfully.")

    except Exception as e:
        logger.critical(f"Job failed with unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if db_engine:
            db_engine.dispose()
            logger.info("Database engine connections disposed.")
        if connector:
            connector.close()
            logger.info("Cloud SQL Connector closed.")

if __name__ == "__main__":
    main()
