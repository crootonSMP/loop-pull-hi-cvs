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
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# --- Configuration Constants ---
LOGIN_URL = "https://clients.hireintelligence.io/login"
MULTI_CANDIDATE_ADMIN_URL = "https://clients.hireintelligence.io/multi-candidate-admin"
GCS_SCREENSHOT_BUCKET_NAME = "recruitment-engine-cvs-sp-260625" # Your actual GCS bucket name

# --- Logging Setup ---
# Setting level to DEBUG to capture all new messages
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Google Cloud Clients ---
storage_client = storage.Client()
secret_client = secretmanager.SecretManagerServiceClient()

# --- Project and Secrets ---
def get_project_id():
    """Resolve GCP project from ADC."""
    try:
        logger.debug("Attempting to determine GCP Project ID...")
        _, project_id = google.auth.default()
        if not project_id:
            logger.critical("Could not determine GCP Project ID. Ensure ADC is configured.")
            raise RuntimeError("Could not determine GCP Project ID")
        logger.info(f"GCP Project ID resolved: {project_id}")
        return project_id
    except Exception as e:
        logger.error(f"Failed to determine GCP Project ID: {e}", exc_info=True)
        raise

GCP_PROJECT_ID = get_project_id()

def get_secret(secret_id: str) -> str:
    """Fetch secret from Secret Manager."""
    name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    logger.debug(f"Attempting to access secret: {name}")
    try:
        payload = secret_client.access_secret_version(request={"name": name}).payload.data
        logger.info(f"Successfully accessed secret: {secret_id}")
        return payload.decode("utf-8").strip()
    except Exception as e:
        logger.error(f"Failed to access secret '{secret_id}': {e}. Ensure service account has Secret Manager Secret Accessor role and secret exists with a version.", exc_info=True)
        raise

def load_config() -> Dict[str, str]:
    """Load configuration from environment variables and Secret Manager."""
    logger.info("Loading configuration...")
    cfg = {}
    try:
        cfg["HIRE_USERNAME"] = os.getenv("HIRE_USERNAME", "").strip()
        logger.info(f"Loaded HIRE_USERNAME from environment: {'present' if cfg['HIRE_USERNAME'] else 'MISSING'}")
        cfg["HIRE_PASSWORD"] = get_secret("hire-password")
    except Exception as e:
        logger.critical(f"Error loading HIRE_PASSWORD secret, cannot proceed: {e}", exc_info=True)
        raise

    if not all([cfg["HIRE_USERNAME"], cfg["HIRE_PASSWORD"]]):
        missing_keys = [k for k, v in cfg.items() if not v]
        logger.critical(f"Missing required configuration values. Check environment variables and Secret Manager. Missing: {missing_keys}")
        raise ValueError("Missing required configuration values for screenshot job.")
    
    logger.info("All essential configuration loaded successfully.")
    return cfg

def get_webdriver():
    """Initializes and returns a headless Chrome WebDriver."""
    logger.info("Initializing headless Chrome WebDriver...")
    options = Options()
    options.add_argument("--headless")
    logger.debug("Added Chrome option: --headless")
    options.add_argument("--no-sandbox")
    logger.debug("Added Chrome option: --no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    logger.debug("Added Chrome option: --disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    logger.debug("Added Chrome option: --window-size=1920,1080")
    options.add_argument("--start-maximized")
    logger.debug("Added Chrome option: --start-maximized")
    options.add_argument("--disable-gpu")
    logger.debug("Added Chrome option: --disable-gpu")
    options.add_argument("--log-level=3")
    logger.debug("Added Chrome option: --log-level=3")
    options.add_argument("--enable-logging")
    logger.debug("Added Chrome option: --enable-logging")
    options.add_argument("--v=1")
    logger.debug("Added Chrome option: --v=1")
    
    # Add an explicit argument to make sure chromedriver logs are suppressed,
    # and only errors are shown to avoid log spam from driver.
    options.add_argument('--disable-logging')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])


    try:
        driver = webdriver.Chrome(options=options)
        logger.debug("WebDriver.Chrome instance created.")
        driver.set_page_load_timeout(60)
        logger.info("Chrome WebDriver initialized with a page load timeout of 60 seconds.")
        return driver
    except WebDriverException as e:
        logger.critical(f"Failed to initialize WebDriver: {e}. This usually indicates a problem with Chrome/Chromedriver installation or compatibility.", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"An unexpected error occurred during WebDriver initialization: {e}", exc_info=True)
        raise

def login_to_hire_intelligence(driver, cfg: Dict[str, str]):
    """Logs into the Hire Intelligence platform."""
    logger.info(f"Navigating to login page: {LOGIN_URL}")
    driver.get(LOGIN_URL)
    logger.debug(f"Current URL after navigation: {driver.current_url}")

    try:
        logger.debug("Waiting for username field (By.NAME, 'Username')...")
        username_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "Username"))
        )
        logger.info("Username field found. Entering username.")
        username_field.send_keys(cfg["HIRE_USERNAME"])

        logger.debug("Waiting for password field (By.NAME, 'Password')...")
        password_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "Password"))
        )
        logger.info("Password field found. Entering password.")
        password_field.send_keys(cfg["HIRE_PASSWORD"])

        logger.debug("Waiting for login button (By.XPATH, //button[@type='submit'])...")
        login_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        logger.info("Login button found. Clicking login button.")
        login_button.click()

        logger.info("Waiting for post-login page elements (e.g., profile link)...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/profile')]"))
        )
        logger.info("Successfully logged in to Hire Intelligence. Profile link found.")
        logger.debug(f"Current URL after login: {driver.current_url}")

    except TimeoutException as e:
        logger.error(f"Login process timed out. A required element was not found or clickable: {e}. Check selectors or page load speed.", exc_info=True)
        # Optionally, take a screenshot here to debug current page state during timeout
        # driver.save_screenshot("/tmp/login_timeout_debug.png")
        # logger.debug("Screenshot taken for login timeout debug.")
        raise
    except NoSuchElementException as e:
        logger.error(f"Login element not found: {e}. Page structure might have changed.", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during login: {e}", exc_info=True)
        raise

def capture_multi_candidate_screenshot(driver, gcs_bucket_name: str):
    """Navigates to Multi Candidate Admin, waits for 'All []' to populate, and takes a screenshot."""
    logger.info(f"Navigating to Multi Candidate Admin page: {MULTI_CANDIDATE_ADMIN_URL}")
    driver.get(MULTI_CANDIDATE_ADMIN_URL)
    logger.debug(f"Current URL after navigation to admin page: {driver.current_url}")

    try:
        logger.info("Waiting for 'All []' count to be populated...")
        all_count_element_xpath = "//label[./span/input[@type='radio' and @value='0']]/span[2]"
        
        logger.debug(f"Waiting for element with XPath: {all_count_element_xpath} to contain 'All ['. Max 45 seconds.")
        WebDriverWait(driver, 45).until(
            EC.text_to_be_present_in_element(
                (By.XPATH, all_count_element_xpath), "All ["
            )
        )
        logger.debug("'All [' part of text found. Now waiting for a number to populate.")

        # Further wait to ensure the number is actually rendered, not just "All []"
        # This lambda checks if the text contains exactly one '[' and one ']', AND has more characters than "All []"
        WebDriverWait(driver, 10).until(
            lambda d: (lambda el_text: el_text.count('[') == 1 and el_text.count(']') == 1 and len(el_text) > len("All []"))(d.find_element(By.XPATH, all_count_element_xpath).text.strip())
        )
        
        current_count_element = driver.find_element(By.XPATH, all_count_element_xpath)
        current_count_text = current_count_element.text
        logger.info(f"Verified 'All' count populated: {current_count_text}")
        logger.debug(f"Full element HTML for 'All count': {current_count_element.get_attribute('outerHTML')}")

        # Pause for 5 seconds as requested, after content is confirmed
        logger.info("Pausing for 5 seconds for visual stability as requested...")
        time.sleep(5)
        logger.debug("Finished 5-second pause.")

        # Generate a unique filename for the screenshot
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        screenshot_filename = f"multi_candidate_admin_{timestamp}.png"
        local_filepath = f"/tmp/{screenshot_filename}"

        logger.info(f"Attempting to take screenshot and save to {local_filepath}...")
        driver.save_screenshot(local_filepath)
        logger.info("Screenshot successfully taken locally.")

        # Upload to GCS
        logger.info(f"Attempting to upload screenshot to GCS bucket: {gcs_bucket_name}/{screenshot_filename}...")
        try:
            bucket = storage_client.bucket(gcs_bucket_name)
            logger.debug(f"Accessed GCS bucket: {gcs_bucket_name}")
            blob = bucket.blob(screenshot_filename)
            logger.debug(f"Created GCS blob object for {screenshot_filename}")
            blob.upload_from_filename(local_filepath)
            logger.info(f"Screenshot uploaded successfully to gs://{gcs_bucket_name}/{screenshot_filename}")
        except Exception as gcs_e:
            logger.error(f"Failed to upload screenshot to GCS: {gcs_e}. Check GCS bucket name, project ID, and service account permissions (Storage Object Creator role).", exc_info=True)
            # Do not re-raise, allow local file cleanup
            # Optionally: If GCS upload is critical, re-raise here to fail the job
            # raise gcs_e
        finally:
            # Clean up local file even if GCS upload fails
            if os.path.exists(local_filepath):
                os.remove(local_filepath)
                logger.info(f"Cleaned up local file: {local_filepath}")
            else:
                logger.warning(f"Local screenshot file not found for cleanup: {local_filepath}")

    except TimeoutException as e:
        logger.error(f"Timed out waiting for 'All []' count to populate or other page elements to load. This might indicate a change in page structure or very slow loading: {e}", exc_info=True)
        # Optionally, take a screenshot here to debug current page state during timeout
        # driver.save_screenshot("/tmp/admin_timeout_debug.png")
        # logger.debug("Screenshot taken for admin page timeout debug.")
        raise
    except NoSuchElementException as e:
        logger.error(f"Required element on admin page not found: {e}. Page structure might have changed.", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during admin page interaction: {e}", exc_info=True)
        raise

def main():
    """Main execution entrypoint for the screenshot job."""
    driver = None
    try:
        cfg = load_config()
        driver = get_webdriver()
        
        login_to_hire_intelligence(driver, cfg)
        capture_multi_candidate_screenshot(driver, GCS_SCREENSHOT_BUCKET_NAME)

        logger.info("✅ Screenshot job completed successfully.")

    except Exception as e:
        logger.critical(f"Job failed with unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if driver:
            logger.info("Closing WebDriver.")
            driver.quit()
            logger.info("WebDriver closed.")

if __name__ == "__main__":
    main()
