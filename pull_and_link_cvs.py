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
import numpy as np

# --- Google Cloud Libraries ---
import google.auth
from google.cloud import storage, secretmanager
from google.cloud.sql.connector import Connector

# --- Database Libraries ---
import sqlalchemy
import pg8000.dbapi
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# --- Configuration Constants ---
GCS_BUCKET_NAME = "recruitment-engine-cvs-sp-260625"
GCS_CV_DIR = "candidate-cvs/"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Google Cloud Clients ---
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient()
connector = Connector()

# --- File Type Mapping ---
CONTENT_TYPE_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

# --- Secrets and Config ---
def get_project_id():
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
    name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        payload = secret_client.access_secret_version(request={"name": name}).payload.data
        return payload.decode("utf-8").strip()
    except Exception as e:
        logger.error(f"Failed to access secret '{secret_id}': {e}")
        raise

def load_config() -> Dict[str, str]:
    logger.info("Loading configuration…")
    cfg = {}
    cfg["HIRE_USERNAME"] = os.getenv("HIRE_USERNAME", "").strip()
    cfg["HIRE_PASSWORD"] = get_secret("hire-password")
    cfg["DB_USER"] = get_secret("db-user")
    cfg["DB_PASS"] = get_secret("db-password")
    cfg["DB_NAME"] = get_secret("db-name")
    cfg["DB_CONNECTION_NAME"] = os.getenv("DB_CONNECTION_NAME", "").strip()
    cfg["DATES"] = os.getenv("DATES", "").strip()
    if not all([cfg["HIRE_USERNAME"], cfg["HIRE_PASSWORD"], cfg["DB_USER"], cfg["DB_PASS"], cfg["DB_NAME"], cfg["DB_CONNECTION_NAME"]]):
        raise ValueError("Missing required configuration values")
    logger.info("All essential configuration loaded successfully.")
    return cfg

# --- DB Setup ---
def get_db_engine(cfg: Dict[str, str]):
    def getconn():
        return connector.connect(
            cfg["DB_CONNECTION_NAME"], driver="pg8000",
            user=cfg["DB_USER"], password=cfg["DB_PASS"], db=cfg["DB_NAME"])
    return sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)

# --- GCS Upload ---
def upload_cv_to_gcs(bucket_name: str, cv_data: bytes, dest_path: str, content_type: str = 'application/pdf'):
    blob = storage_client.bucket(bucket_name).blob(dest_path)
    blob.upload_from_string(cv_data, content_type=content_type)
    logger.info(f"Uploaded CV to gs://{bucket_name}/{dest_path}")
    return f"gs://{bucket_name}/{dest_path}"

# --- API Auth ---
def get_api_auth_token(cfg: Dict[str, str]) -> Optional[str]:
    url = "https://partnersapi.applygateway.com/api/Login/login"
    payload = {"Username": cfg["HIRE_USERNAME"], "Password": cfg["HIRE_PASSWORD"]}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Origin": "https://clients.hireintelligence.io",
        "Content-Type": "application/json",
        "Referer": "https://clients.hireintelligence.io/login"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json().get("data", {}).get("accessToken")
    except Exception as e:
        logger.error(f"API authentication failed: {e}")
        return None

# --- CV Download ---
def download_cv_from_api(cv_id: str, token: str) -> Optional[Dict[str, any]]:
    initial_url = f"https://partnersapi.applygateway.com/api/Candidates/getcv/{cv_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Origin": "https://clients.hireintelligence.io",
        "Referer": "https://clients.hireintelligence.io/",
    }

    try:
        # Step 1: Call API to get redirect or signed URL
        r = requests.get(initial_url, headers=headers, timeout=30, allow_redirects=False)
        
        if r.status_code == 302:
            signed_url = r.headers.get("Location")
        elif r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
            signed_url = r.json().get("data", {}).get("cvUrl")  # Guessing the JSON key
        else:
            logger.error(f"Unexpected response for CV {cv_id}: {r.status_code}, body={r.text}")
            return None

        if not signed_url:
            logger.error(f"No signed URL found for CV {cv_id}")
            return None

        # Step 2: Download actual file from signed URL
        file_resp = requests.get(signed_url, headers={"User-Agent": headers["User-Agent"]}, timeout=30)
        file_resp.raise_for_status()
        content_type = file_resp.headers.get("Content-Type", "application/pdf")
        extension = CONTENT_TYPE_TO_EXTENSION.get(content_type, ".pdf")
        return {
            "data": file_resp.content,
            "content_type": content_type,
            "extension": extension
        }

    except Exception as e:
        logger.error(f"Failed to fetch CV {cv_id}: {e}")
        return None



# --- Main Logic ---
def main():
    db_engine = None
    try:
        cfg = load_config()
        db_engine = get_db_engine(cfg)
        token = get_api_auth_token(cfg)
        if not token:
            sys.exit(1)

        # Determine date range
        today = datetime.now(timezone.utc)
        start = today - timedelta(days=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = today.replace(hour=23, minute=59, second=59, microsecond=999999)

        query_sql = text("""
            SELECT id, email, job_ref_number, created_on, cv_id, first_name, last_name
            FROM candidates_daily_report
            WHERE cv_id IS NOT NULL
            AND (cv_gcs_path IS NULL OR cv_download_status LIKE 'Failed%')
            AND created_on BETWEEN :start AND :end
        """)

        with db_engine.connect() as conn:
            rows = conn.execute(query_sql, {"start": start, "end": end}).fetchall()

        for row in rows:
            row = row._asdict()
            cv_id = row['cv_id']
            if not cv_id:
                continue
            result = download_cv_from_api(cv_id, token)
            status = "Failed"
            gcs_path = None
            if result:
                filename = f"{row['job_ref_number']}-{row['first_name']}-{row['last_name']}-{cv_id}-{int(time.time())}{result['extension']}"
                gcs_path = upload_cv_to_gcs(GCS_BUCKET_NAME, result['data'], GCS_CV_DIR + filename, result['content_type'])
                status = "Downloaded"
            update_sql = text("""
                UPDATE candidates_daily_report
                SET cv_gcs_path = :gcs, cv_download_status = :status
                WHERE id = :id
            """)
            with db_engine.connect() as conn:
                conn.execute(update_sql, {"gcs": gcs_path, "status": status, "id": row['id']})
                conn.commit()

        logger.info("✅ All CV tasks completed successfully.")

    except Exception as e:
        logger.critical(f"Job failed with unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if db_engine:
            db_engine.dispose()
        if connector:
            connector.close()

if __name__ == "__main__":
    main()
