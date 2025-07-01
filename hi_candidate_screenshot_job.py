#!/usr/bin/env python3
import os
import sys
import logging
import time
from datetime import datetime, timezone
from typing import Dict

# --- Google Cloud Libraries ---
import google.auth
from google.cloud import storage, secretmanager

# --- Selenium Libraries ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- Configuration Constants ---
LOGIN_URL = "https://clients.hireintelligence.io/login"
MULTI_CANDIDATE_ADMIN_URL = "https://clients.hireintelligence.io/multi-candidate-admin"
GCS_SCREENSHOT_BUCKET_NAME = "recruitment-engine-cvs-sp-260625"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Google Cloud Clients ---
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient()

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
    """Load configuration from environment variables and Secret Manager."""
    logger.info("Loading configuration...")
    cfg = {}
    try:
        cfg["HIRE_USERNAME"] = os.getenv("HIRE_USERNAME", "").strip()
        cfg["HIRE_PASSWORD"] = get_secret("hire-password")
        logger.info("Successfully loaded HIRE_PASSWORD from Secret Manager.")
    except Exception as e:
        logger.error(f"Error loading HIRE_PASSWORD secret: {e}")
        raise

    if not all([cfg["HIRE_USERNAME"], cfg["HIRE_PASSWORD"]]):
        missing_keys = [k for k, v in cfg.items() if not v]
        logger.error(f"Missing required configuration values. Check environment variables and Secret Manager. Missing: {missing_keys}")
        raise ValueError("Missing required configuration values for screenshot job.")
    
    logger.info("All essential configuration loaded successfully.")
    return cfg

def get_webdriver():
    """Initializes and returns a headless Chrome WebDriver."""
    logger.info("Initializing headless Chrome WebDriver...")
    options = Options()
    options.add_argument("--headless")              # Run in headless mode (no UI)
    options.add_argument("--no-sandbox")            # Bypass OS security model, required for Docker
    options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    options.add_argument("--window-size=1920,1080") # Set a consistent window size for screenshots
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")           # Applicable to older headless Chrome versions
    options.add_argument("--log-level=3")           # Suppress excessive logging
    options.add_argument("--enable-logging")
    options.add_argument("--v=1")

    # Specify the path to chromedriver if it's not in PATH. In our Dockerfile, it's linked to /usr/bin/chromedriver
    # options.binary_location = '/usr/bin/google-chrome-stable' # Already handled by PATH or default location
    # service = webdriver.chrome.service.Service(executable_path='/usr/bin/chromedriver/chromedriver') # Already in PATH

    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60) # Set a page load timeout
        logger.info("Chrome WebDriver initialized.")
        return driver
    except WebDriverException as e:
        logger.error(f"Failed to initialize WebDriver: {e}. Ensure Chromedriver is installed and compatible with Chrome browser.")
        raise

def login_to_hire_intelligence(driver, cfg: Dict[str, str]):
    """Logs into the Hire Intelligence platform."""
    logger.info(f"Navigating to login page: {LOGIN_URL}")
    driver.get(LOGIN_URL)

    try:
        # Wait for username field to be present and fill it
        username_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "Username"))
        )
        username_field.send_keys(cfg["HIRE_USERNAME"])

        # Wait for password field to be present and fill it
        password_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "Password"))
        )
        password_field.send_keys(cfg["HIRE_PASSWORD"])

        # Find and click the login button
        login_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        login_button.click()

        # Wait for successful login (e.g., presence of profile link or logout button)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/profile')]"))
        )
        logger.info("Successfully logged in to Hire Intelligence.")

    except TimeoutException:
        logger.error("Login page elements not found or login timed out. Check selectors or network.")
        raise
    except Exception as e:
        logger.error(f"An error occurred during login: {e}", exc_info=True)
        raise

def capture_multi_candidate_screenshot(driver, _bucket_name: str):
    """Navigates to Multi Candidate Admin, waits for 'All []' to populate, and takes a screenshot."""
    logger.info(f"Navigating to Multi Candidate Admin page: {MULTI_CANDIDATE_ADMIN_URL}")
    driver.get(MULTI_CANDIDATE_ADMIN_URL)

    try:
        # Wait for the "All [X]" element to be present and its text content to change from "All []"
        # We target the specific span element that contains this text
        logger.info("Waiting for 'All []' count to be populated...")
        all_count_element_xpath = "//label[./span/input[@type='radio' and @value='0']]/span[2]" # XPath for the <span> holding "All [X]"
        
        WebDriverWait(driver, 45).until( # Increased timeout for content to load
            EC.text_to_be_present_in_element(
                (By.XPATH, all_count_element_xpath), "All ["
            )
        )
        # Additional wait to ensure the number is rendered, not just the brackets
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, all_count_element_xpath).text.strip().count('[') == 1 and
                      d.find_element(By.XPATH, all_count_element_xpath).text.strip().count(']') == 1 and
                      len(d.find_element(By.XPATH, all_count_element_xpath).text.strip()) > len("All []")
        )
        
        current_count_text = driver.find_element(By.XPATH, all_count_element_xpath).text
        logger.info(f"Verified 'All' count populated: {current_count_text}")

        # Pause for 5 seconds as requested, after content is confirmed
        logger.info("Pausing for 5 seconds for visual stability...")
        time.sleep(5)

        # Generate a unique filename for the screenshot
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        screenshot_filename = f"multi_candidate_admin_{timestamp}.png"
        local_filepath = f"/tmp/{screenshot_filename}" # Save to /tmp for Cloud Run/Functions

        # Take screenshot
        logger.info(f"Taking screenshot and saving to {local_filepath}...")
        driver.save_screenshot(local_filepath)
        logger.info("Screenshot taken.")

        # Upload to 
        logger.info(f"Uploading screenshot to GCS bucket: {gcs_bucket_name}/{screenshot_filename}...")
        bucket = storage_client.bucket(gcs_bucket_name)
        blob = bucket.blob(screenshot_filename)
        blob.upload_from_filename(local_filepath)
        logger.info(f"Screenshot uploaded successfully to gs://{gcs_bucket_name}/{screenshot_filename}")

        # Clean up local file
        os.remove(local_filepath)
        logger.info(f"Cleaned up local file: {local_filepath}")

    except TimeoutException:
        logger.error("Timed out waiting for 'All []' count to populate or page elements to load.")
        raise
    except Exception as e:
        logger.error(f"An error occurred during screenshot capture or GCS upload: {e}", exc_info=True)
        raise

def main():
    """Main execution entrypoint for the screenshot job."""
    driver = None
    try:
        cfg = load_config()
        driver = get_webdriver()
        
        login_to_hire_intelligence(driver, cfg)
        capture_multi_candidate_admin_screenshot(driver, GCS_SCREENSHOT_BUCKET_NAME)

        logger.info("✅ Screenshot job completed successfully.")

    except Exception as e:
        logger.critical(f"Job failed with unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed.")

if __name__ == "__main__":
    main()
