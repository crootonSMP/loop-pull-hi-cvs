#!/usr/bin/env python3
import os
import sys
import logging
import time
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List
from urllib.parse import urlencode

# --- Google Cloud Libraries ---
import google.auth
from google.cloud import storage, secretmanager
from google.cloud.sql.connector import Connector

# --- Database Libraries ---
import sqlalchemy
import pg8000.dbapi
from sqlalchemy.dialects import postgresql
from sqlalchemy import func

# --- Configuration Constants ---
DB_TABLE_NAME = "candidates_daily_report"
CV_BUCKET_NAME = "intelligent-recruitment-cvs"  # Replace with your GCS bucket name

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Google Cloud Clients ---
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient()

# Global connector instance for efficiency
connector = Connector()

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
        logger.error(f"Failed to access secret '{secret_id}': {e}")
        raise

def load_config() -> Dict[str, str]:
    """Load configuration from environment variables and Secret Manager."""
    logger.info("Loading configuration…")
    cfg = {}

    # Database credentials
    try:
        cfg["DB_USER"] = get_secret("db-user")
        cfg["DB_PASS"] = get_secret("db-password")
        cfg["DB_NAME"] = get_secret("db-name")
        logger.info("Successfully loaded DB credentials from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading DB secrets: {e}")
        raise

    cfg["DB_CONNECTION_NAME"] = os.getenv("DB_CONNECTION_NAME", "").strip()
    logger.info(f"Loaded DB_CONNECTION_NAME from environment variable: '{cfg['DB_CONNECTION_NAME']}'")

    # API credentials
    cfg["HIRE_USERNAME"] = os.getenv("HIRE_USERNAME", "").strip()
    try:
        cfg["HIRE_PASSWORD"] = get_secret("hire-password")
        cfg["HIRE_API_KEY"] = get_secret("hire-api-key")  # New secret for CV download API key
        logger.info("Successfully loaded HIRE_PASSWORD and HIRE_API_KEY from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading HIRE secrets: {e}")
        raise

    if not all([cfg["DB_USER"], cfg["DB_PASS"], cfg["DB_NAME"], cfg["DB_CONNECTION_NAME"],
                cfg["HIRE_USERNAME"], cfg["HIRE_PASSWORD"], cfg["HIRE_API_KEY"]]):
        missing_keys = [k for k, v in cfg.items() if not v]
        logger.error(f"Missing required configuration values: {missing_keys}")
        raise ValueError("Missing required configuration values for ETL job.")
    
    logger.info("All essential configuration loaded successfully.")
    return cfg

def get_db_engine(cfg: Dict[str, str]):
    """Creates a SQLAlchemy engine for connecting to Cloud SQL."""
    logger.info(f"Attempting to create connection engine for Cloud SQL instance: {cfg['DB_CONNECTION_NAME']}")
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
            pool_size=5, max_overflow=2, pool_timeout=30, pool_recycle=1800,
        )
        logger.info("Database engine created successfully.")
        return engine
    except Exception as e:
        logger.error(f"Failed to create database connection engine: {e}")
        raise

def create_candidates_table(engine):
    """Create the candidates_daily_report table if it doesn't exist."""
    create_sql = sqlalchemy.text(f"""
    CREATE TABLE IF NOT EXISTS {DB_TABLE_NAME} (
        id SERIAL PRIMARY KEY,
        created_on TIMESTAMP NOT NULL,
        job_ref_number VARCHAR(255) NOT NULL,
        status_id INTEGER NULL,
        app_status VARCHAR(255) NULL,
        supplier_name VARCHAR(255) NULL,
        job_title VARCHAR(255) NULL,
        job_location VARCHAR(255) NULL,
        user_id INTEGER NULL,
        first_name VARCHAR(255) NULL,
        last_name VARCHAR(255) NULL,
        telephone_international_dialing_code VARCHAR(10) NULL,
        telephone VARCHAR(255) NULL,
        email VARCHAR(255) NOT NULL,
        buyer_name VARCHAR(255) NULL,
        buyer_id INTEGER NULL,
        cv_id INTEGER NULL,
        interview BOOLEAN NULL,
        hire BOOLEAN NULL,
        rejected BOOLEAN NULL,
        qualified BOOLEAN NULL,
        note_id INTEGER NULL,
        note TEXT NULL,
        source_system VARCHAR(255) NOT NULL DEFAULT 'HireIntelligence',
        etl_load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cv_gcs_path VARCHAR(512) NULL,
        cv_download_status VARCHAR(50) NULL,
        email_sent_timestamp TIMESTAMP NULL,
        email_status VARCHAR(50) NULL,
        email_error_message TEXT NULL
    );
    """)
    try:
        with engine.connect() as connection:
            connection.execute(create_sql)
            connection.commit()
            logger.info(f"Verified or created table '{DB_TABLE_NAME}'.")

class CVDownloadTool:
    def __init__(self, api_key, token):
        self.base_url = "https://partnersapi.applygateway.com/api/Candidate"
        self.download_url = "https://cvfilemanager.applygateway.com/v1/cv/download"
        self.api_key = api_key
        self.token = token
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        }

    def get_cv_filename(self, buyer_id, cv_id, user_id):
        params = {
            "buyerId": buyer_id,
            "CvId": cv_id,
            "UserId": user_id,
            "loggedInBuyer": buyer_id
        }
        url = f"{self.base_url}/CandidateCombination?{urlencode(params)}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json().get("data", {})
        return data.get("fileName"), data.get("cvFileName")

    def download_cv(self, file_name, cv_file_name):
        params = {
            "apiKey": self.api_key,
            "fileName": file_name
        }
        url = f"{self.download_url}?{urlencode(params)}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.content, cv_file_name

def upload_to_gcs(content, file_name, bucket_name=CV_BUCKET_NAME):
    """Upload CV to Google Cloud Storage and return the GCS path."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"cvs/{file_name}")
        blob.upload_from_string(content, content_type="application/pdf")
        gcs_path = f"gs://{bucket_name}/cvs/{file_name}"
        logger.info(f"Uploaded CV to GCS: {gcs_path}")
        return gcs_path
    except Exception as e:
        logger.error(f"Failed to upload CV to GCS: {e}")
        return None

def fetch_data_from_api(cfg: Dict[str, str]) -> pd.DataFrame:
    """Authenticates with the API, fetches candidate report data for yesterday."""
    logger.info("--- Starting API-Based Candidate Report Fetch ---")
    try:
        # Authenticate
        auth_url = "https://partnersapi.applygateway.com/api/Login/login"
        auth_payload = {"Username": cfg["HIRE_USERNAME"], "Password": cfg["HIRE_PASSWORD"]}
        logger.info(f"Authenticating user {cfg['HIRE_USERNAME']} via API...")
        response = requests.post(auth_url, json=auth_payload, timeout=30)
        response.raise_for_status()
        auth_data = response.json()
        token = auth_data.get("data", {}).get("accessToken")
        buyer_id = auth_data.get("data", {}).get("id")
        user_type = auth_data.get("data", {}).get("userType")

        if not all([token, buyer_id, user_type]):
            logger.error(f"API login failed, missing token, buyer ID, or userType.")
            return pd.DataFrame()
        logger.info("🎉 API authentication successful.")

        # Calculate yesterday's date (UTC)
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        start_of_day = yesterday.strftime("%Y-%m-%d")
        end_of_day = yesterday.strftime("%Y-%m-%d")

        # Fetch data with pagination
        report_url = "https://partnersapi.applygateway.com/api/Candidate/MultiCandidateAdmin"
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Origin": "https://clients.hireintelligence.io"
        }
        all_data = []
        page_no = 1
        while True:
            params = {
                "pageNo": page_no,
                "limit": 100,
                "sortBy": "createdOn",
                "sortDesc": "true",
                "search": "",
                "fromDate": start_of_day,
                "toDate": end_of_day,
                "buyerId": buyer_id,
                "supplierId": "",
                "Quality": "0"
            }
            logger.info(f"Requesting page {page_no} for {start_of_day}")
            start_time = time.time()
            response = requests.get(report_url, headers=headers, params=params, timeout=120)
            end_time = time.time()
            response.raise_for_status()
            logger.info(f"API response received in {end_time - start_time:.2f} seconds")

            data = response.json()
            candidates = data.get("data", [])
            all_data.extend(candidates)
            total_count = data.get("getCount", 0)
            logger.info(f"Retrieved {len(candidates)} candidates, total: {total_count}")

            if len(candidates) < 100 or page_no * 100 >= total_count:
                break
            page_no += 1
            time.sleep(5)

        if not all_data:
            logger.warning(f"No candidate data retrieved for {start_of_day}.")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        df["accessToken"] = token  # Store token for CV download
        df["buyerId"] = buyer_id   # Store buyer_id
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error processing API data: {e}")
        return pd.DataFrame()

def insert_candidate_data(df: pd.DataFrame, engine, cfg: Dict[str, str]):
    """Inserts a Pandas DataFrame into the candidates_daily_report table and downloads CVs."""
    if df.empty:
        logger.info("DataFrame is empty. Skipping DB insert and CV download.")
        return

    # Map API response JSON keys to database snake_case columns
    df.rename(columns={
        "createdOn": "created_on",
        "jobRefNumber": "job_ref_number",
        "statusId": "status_id",
        "appStatus": "app_status",
        "supplierName": "supplier_name",
        "jobTitle": "job_title",
        "jobLocation": "job_location",
        "userId": "user_id",
        "firstName": "first_name",
        "lastName": "last_name",
        "telephoneInternationalDialingCode": "telephone_international_dialing_code",
        "telephone": "telephone",
        "email": "email",
        "buyerName": "buyer_name",
        "buyerId": "buyer_id",
        "cVid": "cv_id",
        "noteId": "note_id",
        "note": "note",
        "interview": "interview",
        "hire": "hire",
        "rejected": "rejected",
        "qualified": "qualified"
    }, inplace=True)

    # Add required columns
    df['source_system'] = 'HireIntelligence'
    df['cv_gcs_path'] = pd.NA
    df['cv_download_status'] = pd.NA

    # Initialize CV downloader
    cv_downloader = CVDownloadTool(cfg["HIRE_API_KEY"], df["accessToken"].iloc[0])

    # Download CVs and upload to GCS
    for index, row in df.iterrows():
        try:
            if pd.notna(row["cv_id"]) and pd.notna(row["user_id"]):
                file_name, cv_file_name = cv_downloader.get_cv_filename(
                    row["buyer_id"], row["cv_id"], row["user_id"]
                )
                if file_name and cv_file_name:
                    content, cv_file_name = cv_downloader.download_cv(file_name, cv_file_name)
                    gcs_path = upload_to_gcs(content, cv_file_name)
                    df.at[index, "cv_gcs_path"] = gcs_path
                    df.at[index, "cv_download_status"] = "Success" if gcs_path else "Failed"
                    logger.info(f"Downloaded and uploaded CV for candidate {row['cv_id']}: {cv_file_name}")
                else:
                    df.at[index, "cv_download_status"] = "Failed - No file name"
                    logger.warning(f"No CV file name for candidate {row['cv_id']}")
            else:
                df.at[index, "cv_download_status"] = "Failed - Missing CV ID or User ID"
                logger.warning(f"Missing CV ID or User ID for candidate at index {index}")
        except Exception as e:
            df.at[index, "cv_download_status"] = f"Failed - {str(e)}"
            logger.error(f"Failed to download CV for candidate {row['cv_id']}: {e}")
        time.sleep(1)  # Respect API rate limits

    # Define columns to insert
    db_insert_columns = [
        "created_on", "job_ref_number", "status_id", "app_status", "supplier_name",
        "job_title", "job_location", "user_id", "first_name", "last_name",
        "telephone_international_dialing_code", "telephone", "email", "buyer_name",
        "buyer_id", "cv_id", "interview", "hire", "rejected", "qualified", "note_id", "note",
        "source_system", "cv_gcs_path", "cv_download_status"
    ]

    # Filter DataFrame
    df_final = df[[col for col in db_insert_columns if col in df.columns]]
    logger.info(f"DataFrame filtered to DB-insertable columns. Rows: {len(df_final)}")

    # Data cleaning
    for col in df_final.select_dtypes(include='object').columns:
        df_final[col] = df_final[col].astype(pd.StringDtype()).replace({'': pd.NA})

    # Normalize email and job_ref_number
    if 'email' in df_final.columns:
        df_final['email'] = df_final['email'].astype(str).str.strip().str.lower()
        logger.info("Normalized 'email' to lowercase.")
    if 'job_ref_number' in df_final.columns:
        df_final['job_ref_number'] = df_final['job_ref_number'].astype(str).str.strip().str.lower()
        logger.info("Normalized 'job_ref_number' to lowercase.")

    for col in ['status_id', 'user_id', 'buyer_id', 'cv_id', 'note_id']:
        if col in df_final.columns:
            df_final[col] = df_final[col].replace({np.nan: pd.NA}).astype(pd.Int64Dtype())

    for col in ['interview', 'hire', 'rejected', 'qualified']:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna(False).astype(pd.BooleanDtype())

    if 'created_on' in df_final.columns:
        df_final['created_on'] = pd.to_datetime(df_final['created_on'], errors='coerce', utc=True)
        initial_rows = len(df_final)
        df_final.dropna(subset=['created_on'], inplace=True)
        if len(df_final) < initial_rows:
            logger.warning(f"Dropped {initial_rows - len(df_final)} rows due to invalid 'created_on'.")
        df_final['created_on'] = df_final['created_on'].dt.floor('S').dt.tz_localize(None)

    if 'job_ref_number' in df_final.columns:
        initial_rows = len(df_final)
        df_final.dropna(subset=['job_ref_number'], inplace=True)
        if len(df_final) < initial_rows:
            logger.warning(f"Dropped {initial_rows - len(df_final)} rows due to missing 'job_ref_number'.")

    if 'email' in df_final.columns:
        initial_rows = len(df_final)
        df_final.dropna(subset=['email'], inplace=True)
        if len(df_final) < initial_rows:
            logger.warning(f"Dropped {initial_rows - len(df_final)} rows due to missing 'email'.")

    logger.info(f"DataFrame prepared. Head:\n{df_final.head()}")
    logger.info(f"DataFrame dtypes:\n{df_final.dtypes}")
    logger.info(f"Final row count: {len(df_final)}")

    metadata = sqlalchemy.MetaData()
    table = sqlalchemy.Table(DB_TABLE_NAME, metadata, autoload_with=engine)

    total_inserted_rows = 0
    update_cols = [
        "status_id", "app_status", "supplier_name", "job_title", "job_location",
        "user_id", "first_name", "last_name", "telephone_international_dialing_code",
        "telephone", "buyer_name", "buyer_id", "cv_id", "interview", "hire",
        "rejected", "qualified", "note_id", "note", "source_system",
        "cv_gcs_path", "cv_download_status"
    ]
    update_cols_in_df = [col for col in update_cols if col in df_final.columns]

    records = df_final.to_dict(orient='records')
    if not records:
        logger.info("No records to insert/update. Skipping DB operation.")
        return

    try:
        with engine.begin() as conn:
            for record in records:
                insert_stmt = postgresql.insert(table).values(record)
                on_conflict_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[
                        func.lower(table.c.email),
                        func.lower(table.c.job_ref_number),
                        table.c.created_on
                    ],
                    set_={col: getattr(insert_stmt.excluded, col) for col in update_cols_in_df}
                )
                result = conn.execute(on_conflict_stmt)
                if result.rowcount == 1:
                    total_inserted_rows += 1
                else:
                    logger.warning(f"Unexpected rowcount for UPSERT (email: {record.get('email')}).")

        logger.info(f"Total rows processed: {len(df_final)}. Affected rows: {total_inserted_rows}.")
    except Exception as e:
        logger.error(f"Failed during bulk UPSERT: {e}")
        raise

def main():
    """Main execution entrypoint for the job."""
    db_engine = None
    try:
        cfg = load_config()
        db_engine = get_db_engine(cfg)
        create_candidates_table(db_engine)

        df_api_data = fetch_data_from_api(cfg)

        if df_api_data.empty:
            logger.info("✅ API fetch returned no data. Exiting successfully.")
            sys.exit(0)

        logger.info(f"API data contains {len(df_api_data)} rows. Starting insertion and CV download.")

        insert_candidate_data(df_api_data, db_engine, cfg)

        logger.info("✅ All tasks completed successfully.")

    except Exception as e:
        logger.critical(f"Job failed: {e}")
        sys.exit(1)
    finally:
        if connector:
            connector.close()
            logger.info("Cloud SQL Connector closed.")
        if db_engine:
            db_engine.dispose()
            logger.info("Database engine connections disposed.")

if __name__ == "__main__":
    main()
