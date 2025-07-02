import os
import time
import signal
import subprocess
import traceback
from datetime import datetime
from typing import Optional
import logging
from dataclasses import dataclass
from io import BytesIO

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# Google Cloud
from google.cloud import storage
from google.cloud import secretmanager  # Added for apiKey

# Requests for API calls
import requests

# Load environment variables
load_dotenv()

# Enhanced Configuration
@dataclass
class Config:
    username: str = os.getenv('HIRE_USERNAME', '')
    password: str = os.getenv('HIRE_PASSWORD', '')
    headless: bool = os.getenv('HEADLESS', 'true').lower() == 'true'
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '120'))  # Increased to 2 minutes
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
    screenshot_bucket: str = os.getenv('DEBUG_SCREENSHOT_BUCKET', 'recruitment-engine-cvs-sp-260625')

    def validate(self):
        if not all([self.username, self.password]):
            raise ValueError("Missing credentials in environment variables")
        if not os.path.exists(self.chrome_driver_path):
            raise FileNotFoundError(f"Chromedriver not found at {self.chrome_driver_path}")
        return self

# Enhanced Logging
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # More verbose logging
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def setup_driver(config: Config) -> webdriver.Chrome:
    """Initialize WebDriver with enhanced options"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    if config.headless:
        chrome_options.add_argument('--headless=new')
    
    service = Service(
        executable_path=config.chrome_driver_path,
        service_args=['--verbose', '--log-path=/tmp/chromedriver.log']
    )
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        logger.error(f"Driver initialization failed: {str(e)}")
        raise

def upload_screenshot(driver: webdriver.Chrome, config: Config, name: str) -> bool:
    """Capture and upload screenshot with error handling"""
    try:
        screenshot = driver.get_screenshot_as_png()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"screenshots/{name}_{timestamp}.png"
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(config.screenshot_bucket)
        blob = bucket.blob(blob_name)
        
        with BytesIO(screenshot) as image_stream:
            blob.upload_from_file(image_stream, content_type='image/png')
        
        logger.info(f"Uploaded screenshot: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {str(e)}")
        return False

def upload_file_to_gcs(file_content: BytesIO, config: Config, destination_blob_name: str) -> bool:
    """Upload a file (e.g., CV) to GCS"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(config.screenshot_bucket)
        blob = bucket.blob(destination_blob_name)
        file_content.seek(0)
        # Set content type based on file (default to PDF, adjust later if needed)
        blob.upload_from_file(file_content, content_type='application/pdf')
        logger.info(f"Uploaded file to: gs://{config.screenshot_bucket}/{destination_blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        return False

def get_secret(secret_id: str) -> str:
    """Fetch secret from Secret Manager"""
    name = f"projects/{get_project_id()}/secrets/{secret_id}/versions/latest"
    payload = secret_client.access_secret_version(request={"name": name}).payload.data
    return payload.decode("utf-8").strip()

def get_project_id():
    """Resolve GCP project from ADC"""
    import google.auth
    _, project_id = google.auth.default()
    if not project_id:
        raise RuntimeError("Could not determine GCP Project ID")
    return project_id

def download_cv(cv_id: int, config: Config) -> tuple[str, BytesIO]:
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
        # Extract cookies from Selenium session for authentication (if needed)
        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        response = requests.get(metadata_url, params=params, cookies=cookies, timeout=30)
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

def perform_login(driver: webdriver.Chrome, config: Config) -> bool:
    """Simplified login flow with screenshots and dynamic element handling"""
    login_success = False
    try:
        # Step 1: Navigate to login page
        driver.get("https://clients.hireintelligence.io/login")
        time.sleep(2)  # Allow initial load
        logger.info("Navigated to login page")
        upload_screenshot(driver, config, "login_page")

        # Step 2: Wait for the form to load with longer timeout
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        logger.debug("Login form detected")

        # Step 3: Find email field with multiple attempts
        email = None
        for attempt in range(3):
            try:
                email = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))
                )
                break
            except:
                try:
                    email = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
                    break
                except:
                    try:
                        email = driver.find_element(By.XPATH, "//input[contains(@id, 'email')]")
                        break
                    except:
                        if attempt < 2:
                            time.sleep(2)
                            continue
                        raise
        email.send_keys(config.username)
        logger.debug("Entered username")

        # Step 4: Find password field
        password = None
        for attempt in range(3):
            try:
                password = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
                break
            except:
                try:
                    password = driver.find_element(By.XPATH, "//input[@type='password']")
                    break
                except:
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    raise
        password.send_keys(config.password)
        logger.debug("Entered password")

        # Step 5: Submit form
        submit = None
        for attempt in range(3):
            try:
                submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                break
            except:
                try:
                    submit = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
                    break
                except:
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    raise
        submit.click()
        logger.debug("Clicked submit button")

        # Step 6: Verify login success with fallback
        WebDriverWait(driver, config.explicit_wait).until(
            EC.url_contains("clients.hireintelligence.io")
        )
        login_success = True
        logger.info("Login successful")
        upload_screenshot(driver, config, "login_success")
        return True

    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        logger.debug(f"Full page source:\n{driver.page_source}")  # Log full source
        logger.debug(f"Stack trace:\n{traceback.format_exc()}")
        upload_screenshot(driver, config, "login_failed")
        return False
    finally:
        if login_success and upload_screenshot(driver, config, "login_success"):
            return True
        return False

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info("Starting screenshot and CV capture job")
        
        driver = setup_driver(config)
        
        # 1. Login flow
        if not perform_login(driver, config):
            logger.warning("Login attempt failed, but proceeding with navigation - check screenshots")
        else:
            logger.info("Login succeeded, proceeding with navigation")
        
        # 2. Capture dashboard with wait
        driver.get("https://clients.hireintelligence.io/")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        upload_screenshot(driver, config, "dashboard")
        
        # 3. Capture admin page
        try:
            driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
            WebDriverWait(driver, config.explicit_wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            upload_screenshot(driver, config, "multi_candidate_admin")
            logger.info("Captured multi-candidate-admin page")
        except Exception as e:
            logger.error(f"Failed to navigate to multi-candidate-admin: {str(e)}")
            upload_screenshot(driver, config, "multi_candidate_admin_failed")
        
        # 4. Download CV (proof-of-concept)
        cv_ids = [5620275]  # Start with one CV
        for cv_id in cv_ids:
            cv_file_name, file_content = download_cv(cv_id, config)
            if cv_file_name and file_content:
                destination_blob_name = f"cvs/{cv_file_name}"
                if upload_file_to_gcs(file_content, config, destination_blob_name):
                    logger.info(f"Successfully processed CV {cv_id}")
                time.sleep(1)  # Respect server load with 1-second delay
        
        logger.info("Job completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Job failed: {str(e)}")
        logger.debug(f"Stack trace:\n{traceback.format_exc()}")
        return 1
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser terminated")
            except Exception as e:
                logger.error(f"Error quitting browser: {str(e)}")
                subprocess.run(["pkill", "-9", "-f", "chrome"], stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    exit(main())
