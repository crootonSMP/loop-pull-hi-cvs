import os
import time
import logging
import requests
from io import BytesIO
from datetime import datetime

# Google Cloud
from google.cloud import storage
from google.cloud import secretmanager
import google.auth

# Load environment variables
from dotenv import load_dotenv  # Added import for load_dotenv

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Google Cloud Clients
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient()

def get_project_id():
    """Resolve GCP project from ADC"""
    _, project_id = google.auth.default()
    if not project_id:
        raise RuntimeError("Could not determine GCP Project ID")
    return project_id

GCP_PROJECT_ID = get_project_id()

def get_secret(secret_id: str) -> str:
    """Fetch secret from Secret Manager"""
    name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    payload = secret_client.access_secret_version(request={"name": name}).payload.data
    return payload.decode("utf-8").strip()

def upload_file_to_gcs(file_content: BytesIO, bucket_name: str, destination_blob_name: str) -> bool:
    """Upload a file (e.g., CV) to GCS"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        file_content.seek(0)
        # Set content type based on file (default to PDF, adjust later)
        blob.upload_from_file(file_content, content_type='application/pdf')
        logger.info(f"Uploaded file to: gs://{bucket_name}/{destination_blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        return False

def download_cv(cv_id: int) -> tuple[str, BytesIO]:
    """Download a CV using the API"""
    api_key = get_secret("CV_DOWNLOAD_API_KEY")
    
    # Step 1: Fetch CV metadata
    metadata_url = "https://partnersapi.applygateway.com/api/Candidate/CandidateCombination"
    params = {
        "buyerId": "1061",
        "CvId": cv_id,
        "UserId": "5414048",
        "loggedInBuyer": "1061"
    }
    try:
        response = requests.get(metadata_url, params=params, timeout=30)
        response.raise_for_status()
        metadata = response.json()
        file_name = metadata["data"]["fileName"]
        cv_file_name = metadata["data"]["cvFileName"]  # e.g., "James-Mason-5620275.pdf"
        logger.info(f"Retrieved metadata for CV {cv_id}: {cv_file_name}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch CV metadata for {cv_id}: {e}")
        return None, None

    # Step 2: Download CV
    download_url = "https://cvfilemanager.applygateway.com/v1/cv/download"
    params = {
        "apiKey": api_key,
        "fileName": file_name
    }
    try:
        response = requests.get(download_url, params=params, timeout=30, stream=True)
        response.raise_for_status()
        file_content = BytesIO(response.content)
        logger.info(f"Downloaded CV for {cv_id}")
        return cv_file_name, file_content
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download CV for {cv_id}: {e}")
        return None, None

def main():
    load_dotenv()  # Load environment variables
    bucket_name = "recruitment-engine-cvs-sp-260625"
    cv_ids = [5620275]  # Proof-of-concept with one CV

    for cv_id in cv_ids:
        cv_file_name, file_content = download_cv(cv_id)
        if cv_file_name and file_content:
            destination_blob_name = f"cvs/{cv_file_name}"
            if upload_file_to_gcs(file_content, bucket_name, destination_blob_name):
                logger.info(f"Successfully processed CV {cv_id}")
            time.sleep(1)  # Respect server load with 1-second delay

    logger.info("Job completed")

if __name__ == "__main__":
    main()
