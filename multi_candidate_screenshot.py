#!/usr/bin/env python3
import os
import sys
import logging
import time
import requests # Kept from original, though not directly used in this script
from datetime import datetime, timezone, timedelta
import pandas as pd # Kept from original, though not directly used in this script
import numpy as np # Kept from original, though not directly used in this script
from typing import Dict, List
import tempfile # For temporary file storage

# --- Google Cloud Libraries ---
import google.auth
from google.cloud import storage, secretmanager

# We don't need these database libraries for just a screenshot,
# but keeping them imported for consistency with your broader project
# from google.cloud.sql.connector import Connector
# import sqlalchemy
# import pg8000.dbapi
# from sqlalchemy.dialects import postgresql
# from sqlalchemy import func

# --- Selenium Libraries ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- Configuration Constants ---
# DB_TABLE_NAME = "candidates_daily_report" # Not used in this specific script

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Google Cloud Clients ---
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient()

# Global connector instance for efficiency (commented out as per new script focus)
# connector = Connector()

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
# Replace with your GCS bucket name for screenshots
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "your-screenshot-bucket-name")


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
    """Load configuration from environment variables and Secret Manager."""
    logger.info("Loading configuration…")
    cfg = {}

    try:
        cfg["HIRE_USERNAME"] = os.getenv("HIRE_USERNAME", "").strip()
        cfg["HIRE_PASSWORD"] = get_secret("hire-password") # Using Secret Manager
        logger.info("Successfully loaded HIRE_USERNAME from env and HIRE_PASSWORD from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading HIRE_USERNAME or HIRE_PASSWORD: {e}")
        raise

    if not all([cfg["HIRE_USERNAME"], cfg["HIRE_PASSWORD"]]):
        missing_keys = [k for k, v in cfg.items() if not v]
        logger.error(f"Missing required configuration values. Check environment variables and Secret Manager. Missing: {missing_keys}")
        raise ValueError("Missing required configuration values for screenshot job.")
        
    if not GCS_BUCKET_NAME or GCS_BUCKET_NAME == "your-screenshot-bucket-name":
        logger.error("GCS_BUCKET_NAME environment variable is not set or still default. Please configure it.")
        raise ValueError("GCS_BUCKET_NAME not configured.")

    logger.info(f"All essential configuration loaded successfully. GCS Bucket: {GCS_BUCKET_NAME}")
    return cfg

def initialize_webdriver():
    """Initializes a headless Chrome WebDriver."""
    logger.info("Initializing headless Chrome WebDriver...")
    options = Options()
    options.add_argument("--headless") # Run in headless mode
    options.add_argument("--no-sandbox") # Bypass OS security model, required for Docker
    options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    options.add_argument("--window-size=1920,1080") # Set a consistent window size for screenshots
    options.add_argument("--disable-gpu") # Recommended for headless mode
    options.add_argument("--log-level=3") # Suppress verbose logging
    options.add_argument("--incognito") # Browse in incognito mode (optional)
    options.add_argument("--disable-features=NetworkService") # Sometimes helps with stability
    options.add_argument("--single-process") # For some environments, single process is better

    try:
        driver = webdriver.Chrome(options=options)
        logger.info("Chrome WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        logger.error(f"Failed to initialize WebDriver: {e}", exc_info=True)
        logger.error("Ensure `chromium-driver` is installed and available in PATH.")
        sys.exit(1)

def login_to_hire_intelligence(driver: webdriver.Chrome, cfg: Dict[str, str]):
    """Logs into the Hire Intelligence platform."""
    LOGIN_URL = "https://clients.hireintelligence.io/login"
    logger.info(f"Navigating to login page: {LOGIN_URL}")
    driver.get(LOGIN_URL)

    try:
        # Wait for username field to be present
        username_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "username")) # Assuming ID is 'username' or similar
        )
        password_field = driver.find_element(By.ID, "password") # Assuming ID is 'password'

        username_field.send_keys(cfg["HIRE_USERNAME"])
        password_field.send_keys(cfg["HIRE_PASSWORD"])

        # Click the login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']") # Assuming type='submit'
        login_button.click()
        logger.info("Login credentials entered and login button clicked.")

        # Wait for a successful login. We'll wait for the "Logout" button or profile link to appear
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Logout')]"))
        )
        logger.info("Successfully logged in.")

    except TimeoutException:
        logger.error("Login page elements not found or login timed out.")
        raise
    except Exception as e:
        logger.error(f"An error occurred during login: {e}", exc_info=True)
        raise

def capture_multi_candidate_screenshot(driver: webdriver.Chrome, gcs_bucket: str):
    """Navigates to the multi-candidate-admin page, waits for content, and takes a screenshot."""
    MULTI_CANDIDATE_ADMIN_URL = "https://clients.hireintelligence.io/multi-candidate-admin"
    logger.info(f"Navigating to multi-candidate-admin page: {MULTI_CANDIDATE_ADMIN_URL}")
    driver.get(MULTI_CANDIDATE_ADMIN_URL)

    try:
        # Wait for the "All [X]" count to be populated
        # The XPath targets the <span> that contains "All [" and then a number
        # based on the provided HTML structure.
        logger.info("Waiting for 'All [X]' element to be populated...")
        all_count_element = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located((By.XPATH, "//label[contains(@class, 'ant-radio-wrapper')]/span[2][starts-with(text(), 'All [')]"))
        )
        logger.info(f"Found 'All [X]' element: {all_count_element.text}")

        # As requested, an additional 5-second pause for good measure (though explicit waits are generally preferred)
        logger.info("Pausing for 5 seconds for full page rendering...")
        time.sleep(5)

        # Generate a unique filename for the screenshot
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        screenshot_filename = f"multi_candidate_admin_{timestamp}.png"
        local_screenshot_path = os.path.join(tempfile.gettempdir(), screenshot_filename)

        # Take screenshot
        logger.info(f"Taking screenshot and saving to temporary file: {local_screenshot_path}")
        driver.save_screenshot(local_screenshot_path)

        # Upload to GCS
        bucket = storage_client.bucket(gcs_bucket)
        blob = bucket.blob(screenshot_filename)
        logger.info(f"Uploading screenshot '{screenshot_filename}' to GCS bucket '{gcs_bucket}'...")
        blob.upload_from_filename(local_screenshot_path)
        logger.info(f"Screenshot uploaded to gs://{gcs_bucket}/{screenshot_filename}")

        # Clean up local temporary file
        os.remove(local_screenshot_path)
        logger.info(f"Local temporary file '{local_screenshot_path}' removed.")

    except TimeoutException:
        logger.error("Timed out waiting for elements on multi-candidate-admin page.")
        raise
    except Exception as e:
        logger.error(f"An error occurred during screenshot capture or upload: {e}", exc_info=True)
        raise

def main():
    """Main execution entrypoint for the job."""
    driver = None
    try:
        cfg = load_config()
        
        # Initialize WebDriver
        driver = initialize_webdriver()

        # Login
        login_to_hire_intelligence(driver, cfg)

        # Capture screenshot
        capture_multi_candidate_screenshot(driver, GCS_BUCKET_NAME)

        logger.info("✅ All tasks completed successfully.")

    except Exception as e:
        logger.critical(f"Job failed with unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if driver:
            driver.quit()
            logger.info("Chrome WebDriver closed.")

if __name__ == "__main__":
    main()
