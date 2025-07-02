import os
import time
import signal
import subprocess
from datetime import datetime
import logging
from dataclasses import dataclass
from io import BytesIO
from contextlib import contextmanager

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException,
                                      WebDriverException,
                                      TimeoutException)

# Google Cloud and other imports
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
@dataclass
class Config:
    username: str = os.getenv('HIRE_USERNAME', '')
    password: str = os.getenv('HIRE_PASSWORD', '')
    headless: bool = os.getenv('HEADLESS', 'true').lower() == 'true'
    implicit_wait: int = int(os.getenv('IMPLICIT_WAIT', '10'))
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '30'))
    output_dir: str = os.getenv('OUTPUT_DIR', 'output') # This might not be strictly needed for GCS direct upload
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
    screen_width: int = int(os.getenv('SCREEN_WIDTH', '1920'))
    screen_height: int = int(os.getenv('SCREEN_HEIGHT', '1080'))
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    retry_delay: int = int(os.getenv('RETRY_DELAY', '5'))
    screenshot_bucket: str = os.getenv('DEBUG_SCREENSHOT_BUCKET', 'recruitment-engine-cvs-sp-260625')

    def validate(self):
        """Validate configuration and credentials"""
        if not self.username or not self.password:
            raise ValueError("Missing credentials in environment variables")
        # os.makedirs(self.output_dir, exist_ok=True) # Not strictly needed if not saving local files
        if not os.path.exists(self.chrome_driver_path):
            raise FileNotFoundError(f"Chromedriver not found at {self.chrome_driver_path}")
        return self

# Initialize logging
def setup_logging() -> logging.Logger:
    """Configure logging with file rotation and proper formatting"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation (might not be accessible in some Cloud Run configs)
    file_handler = logging.FileHandler('scraper.log')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler (recommended for Cloud Run logs)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()

@contextmanager
def resource_manager(resource_name: str):
    """Context manager for resource cleanup"""
    try:
        yield
    except Exception as e:
        logger.error(f"Error occurred while managing {resource_name}: {str(e)}")
        raise
    finally:
        logger.debug(f"Cleaning up {resource_name} resources")

def verify_chrome_installation(config: Config) -> tuple[bool, str]:
    """Verify Chrome and Chromedriver are properly installed and compatible"""
    try:
        with resource_manager("Chrome version check"):
            chrome_version_output = subprocess.run(
                ["google-chrome", "--version"],
                check=True,
                capture_output=True,
                text=True
            ).stdout.strip()

            chrome_version = chrome_version_output.split()[-1]

        with resource_manager("Chromedriver version check"):
            driver_version_output = subprocess.run(
                [config.chrome_driver_path, "--version"],
                check=True,
                capture_output=True,
                text=True
            ).stdout.strip()

            driver_version = driver_version_output.split()[1]

        # Verify version compatibility
        if chrome_version.split('.')[0] != driver_version.split('.')[0]:
            msg = (f"Version mismatch: Chrome {chrome_version} vs "
                  f"Chromedriver {driver_version}")
            logger.error(msg)
            return False, msg

        logger.info(f"Verified Chrome {chrome_version} and Chromedriver {driver_version}")
        return True, "Version check passed"

    except subprocess.CalledProcessError as e:
        error_msg = f"Process execution failed: {e.stderr.strip()}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected verification error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def setup_driver(config: Config) -> webdriver.Chrome:
    """Configure and initialize Chrome WebDriver with robust options"""
    for attempt in range(config.max_retries):
        try:
            logger.info(f"Initializing WebDriver (attempt {attempt + 1}/{config.max_retries})")

            chrome_options = Options()

            # Essential configuration for containerized environments
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument(f'--window-size={config.screen_width},{config.screen_height}')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-setuid-sandbox')
            chrome_options.add_argument('--remote-debugging-port=9222') # Useful for local debugging

            # Headless configuration
            if config.headless:
                chrome_options.add_argument('--headless=new')

            # Configure service with error handling
            service = Service(
                executable_path=config.chrome_driver_path,
                service_args=['--verbose'] # Keep verbose for more detailed chromedriver logs
            )

            # Additional stability parameters
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options,
                # service_log_path=os.path.join(config.output_dir, 'chromedriver.log') # May not be persistent in Cloud Run
            )

            # Basic verification
            driver.get('about:blank')
            if not driver.title == '': # Simple check to ensure driver is responsive
                raise RuntimeError("Driver verification failed: Could not load about:blank")

            driver.implicitly_wait(config.implicit_wait)
            logger.info("WebDriver initialized successfully")
            return driver

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == config.max_retries - 1:
                logger.critical("Max retries reached for WebDriver initialization")
                raise RuntimeError("Failed to initialize WebDriver after multiple attempts") from e
            time.sleep(config.retry_delay)

def cleanup_driver(driver: webdriver.Chrome) -> None:
    """Properly cleanup WebDriver resources"""
    if driver is None:
        return

    try:
        driver.quit()
        logger.info("Browser terminated gracefully")
    except Exception as e:
        logger.warning(f"Error during driver quit: {str(e)}")
        try:
            # Fallback cleanup
            if hasattr(driver, 'service') and driver.service.process:
                driver.service.process.send_signal(signal.SIGTERM)
                time.sleep(1)
                if driver.service.process.poll() is None:
                    driver.service.process.kill()
        except Exception as kill_error:
            logger.error(f"Failed to kill driver process: {str(kill_error)}")
    finally:
        # Force cleanup of any remaining processes
        subprocess.run(["pkill", "-9", "-f", "chrome"], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-9", "-f", "chromedriver"], stderr=subprocess.DEVNULL)

def upload_screenshot_to_gcs(bucket_name: str, image_data: bytes, destination_blob_name: str) -> None:
    """Uploads bytes data (screenshot) to the Google Cloud Storage bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_file(BytesIO(image_data), content_type='image/png')
        logger.info(f"Screenshot uploaded to gs://{bucket_name}/{destination_blob_name}.")
    except Exception as e:
        logger.error(f"Failed to upload screenshot to GCS bucket {bucket_name}: {str(e)}")
        raise

def login_to_hireintelligence(driver: webdriver.Chrome, config: Config):
    """Logs into the Hire Intelligence platform."""
    logger.info("Navigating to login page: https://clients.hireintelligence.io/login")
    driver.get("https://clients.hireintelligence.io/login")

    try:
        # Wait for the email input field to be present
        email_field = WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        logger.info("Login page loaded. Entering credentials.")

        # Locate password field and login button
        password_field = driver.find_element(By.NAME, "password")
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']") # More robust selector based on common button types

        email_field.send_keys(config.username)
        password_field.send_keys(config.password)
        
        # Click the login button
        login_button.click()

        logger.info("Login button clicked. Waiting for dashboard URL to load.")
        # Wait for the URL to change to the main dashboard after login
        WebDriverWait(driver, config.explicit_wait).until(
            EC.url_contains("https://clients.hireintelligence.io/")
        )
        logger.info("Successfully logged into Hire Intelligence.")

    except TimeoutException as e:
        logger.error(f"Timeout while waiting for login elements or dashboard after login: {e}")
        # Optionally take a screenshot here for debugging login issues
        # take_and_upload_screenshot(driver, config, "login_timeout_debug")
        raise
    except NoSuchElementException as e:
        logger.error(f"Could not find login elements (email, password, or login button): {e}")
        # Optionally take a screenshot here for debugging missing elements
        # take_and_upload_screenshot(driver, config, "login_elements_missing_debug")
        raise
    except Exception as e:
        logger.critical(f"An unexpected error occurred during login: {e}", exc_info=True)
        raise

def take_and_upload_screenshot(driver: webdriver.Chrome, config: Config, page_label: str):
    """Takes a screenshot and uploads it to GCS."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_bytes = driver.get_screenshot_as_png()
    gcs_blob_name = f"screenshots/{page_label}_{timestamp}.png" # Organize in 'screenshots' folder in GCS

    logger.info(f"Uploading screenshot for {page_label} to GCS bucket {config.screenshot_bucket} as {gcs_blob_name}")
    upload_screenshot_to_gcs(config.screenshot_bucket, screenshot_bytes, gcs_blob_name)
    logger.info(f"Screenshot for {page_label} uploaded successfully.")


def main() -> int:
    driver = None
    try:
        config = Config().validate() # Initialize and validate config here
        logger.info(f"Starting scraping job with configuration: {config}")

        # Verify Chrome installation before starting the driver
        is_chrome_ok, msg = verify_chrome_installation(config)
        if not is_chrome_ok:
            logger.critical(f"Chrome/Chromedriver verification failed: {msg}")
            return 1

        driver = setup_driver(config)

        # 1. Log in to Hire Intelligence
        login_to_hireintelligence(driver, config)

        # 2. Wait for job count on home page and take screenshot
        logger.info("Currently on dashboard. Waiting for job count element to appear.")
        try:
            # Wait for text content that matches the pattern "X Jobs Listed"
            # This XPath looks for any element containing the text "Jobs Listed"
            # It's important to understand the actual HTML structure. If the number
            # is part of a span or div with a specific class, target that.
            # For now, a generic contains() check on all text is used.
            WebDriverWait(driver, config.explicit_wait).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Jobs Listed')]"))
            )
            logger.info("'Jobs Listed' text found on the dashboard.")
            take_and_upload_screenshot(driver, config, "hireintelligence_home")
        except TimeoutException as e:
            logger.warning(f"Timeout while waiting for 'Jobs Listed' text on the dashboard: {e}. Taking screenshot anyway.")
            take_and_upload_screenshot(driver, config, "hireintelligence_home_no_job_count") # Take anyway with a different name
        except Exception as e:
            logger.error(f"Error while waiting for job count: {e}", exc_info=True)
            take_and_upload_screenshot(driver, config, "hireintelligence_home_error") # Take screenshot on error too


        # 3. Go to multi-candidate-admin page and take screenshot
        logger.info("Navigating to multi-candidate-admin page: https://clients.hireintelligence.io/multi-candidate-admin")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")

        # Wait for some element specific to the multi-candidate-admin page to ensure it's loaded
        # The generic 'body' element is a fallback. If there's a unique header,
        # table, or button on this page, use that selector for better reliability.
        try:
            WebDriverWait(driver, config.explicit_wait).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")) # Placeholder: Replace with a more specific element
            )
            logger.info("Multi-candidate-admin page loaded.")
            take_and_upload_screenshot(driver, config, "hireintelligence_multi_candidate_admin")
        except TimeoutException as e:
            logger.warning(f"Timeout while waiting for multi-candidate-admin page to load: {e}. Taking screenshot anyway.")
            take_and_upload_screenshot(driver, config, "hireintelligence_multi_candidate_admin_timeout")
        except Exception as e:
            logger.error(f"Error while waiting for multi-candidate-admin page: {e}", exc_info=True)
            take_and_upload_screenshot(driver, config, "hireintelligence_multi_candidate_admin_error")


        logger.info("Job completed successfully")
        return 0

    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        cleanup_driver(driver)

if __name__ == "__main__":
    exit(main())
