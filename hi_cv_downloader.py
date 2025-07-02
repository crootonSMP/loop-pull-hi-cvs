import os
import time
import signal
import subprocess
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
from dataclasses import dataclass
from io import BytesIO
import requests
from urllib.parse import urlencode

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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enhanced Configuration
@dataclass
class Config:
    username: str = os.getenv('HIRE_USERNAME', '')
    password: str = os.getenv('HIRE_PASSWORD', '')
    api_key: str = os.getenv('REACT_APP_CV_DOWNLOAD_API_KEY', '')
    screenshot_bucket: str = os.getenv('DEBUG_SCREENSHOT_BUCKET', 'recruitment-engine-cvs-sp-260625')
    cv_bucket: str = os.getenv('CV_BUCKET', 'recruitment-engine-cvs')
    headless: bool = os.getenv('HEADLESS', 'true').lower() == 'true'
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '120'))
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')

    def validate(self):
        if not all([self.username, self.password, self.api_key]):
            raise ValueError("Missing credentials or API key in environment variables")
        if not os.path.exists(self.chrome_driver_path):
            raise FileNotFoundError(f"Chromedriver not found at {self.chrome_driver_path}")
        return self

# Enhanced Logging
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
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

def upload_file_to_gcs(config: Config, file_content: bytes, blob_name: str, content_type: str = 'application/pdf') -> bool:
    """Upload file to GCS with error handling"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(config.cv_bucket)
        blob = bucket.blob(blob_name)
        with BytesIO(file_content) as file_stream:
            blob.upload_from_file(file_stream, content_type=content_type)
        logger.info(f"Uploaded file to GCS: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {str(e)}")
        return False

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

def perform_login(driver: webdriver.Chrome, config: Config) -> bool:
    """Simplified login flow with screenshots and dynamic element handling"""
    login_success = False
    try:
        driver.get("https://clients.hireintelligence.io/login")
        time.sleep(2)
        logger.info("Navigated to login page")
        upload_screenshot(driver, config, "login_page")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        logger.debug("Login form detected")
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
        WebDriverWait(driver, config.explicit_wait).until(
            EC.url_contains("clients.hireintelligence.io")
        )
        login_success = True
        logger.info("Login successful")
        upload_screenshot(driver, config, "login_success")
        return True
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        logger.debug(f"Full page source:\n{driver.page_source}")
        logger.debug(f"Stack trace:\n{traceback.format_exc()}")
        upload_screenshot(driver, config, "login_failed")
        return False
    finally:
        if login_success and upload_screenshot(driver, config, "login_success"):
            return True
        return False

def get_yesterdays_cvs(driver: webdriver.Chrome, config: Config, buyer_id: str = "1061") -> List[Dict]:
    """Fetch CVs from yesterday using the date picker and table"""
    cv_list = []
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")  # 2025-07-01
    try:
        logger.info(f"Fetching CVs for {yesterday}")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        upload_screenshot(driver, config, "multi_candidate_admin")

        # Set date picker (placeholder selector; adjust based on inspection)
        date_picker = WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='date']"))  # Adjust selector
        )
        date_picker.clear()
        date_picker.send_keys(yesterday)
        logger.debug("Date filter set to yesterday")

        # Wait for table to update
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tr"))  # Adjust selector
        )

        # Extract data from table rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")  # Adjust selector
        for row in rows[1:]:  # Skip header row
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 7:  # Ensure enough columns (Date, App Status, Ref, Job Title, Location, Supplier, Candidate)
                    date_text = cells[0].text.strip()  # "2025-06-29 3:02 pm"
                    if not date_text.startswith(yesterday):  # Filter for yesterday
                        continue
                    candidate_text = cells[6].text.strip()  # "Serah Adelakun [email protected] +44 7366687182"
                    names = candidate_text.split()[0:2]  # Split to get first and last name
                    first_name = names[0] if len(names) > 0 else ""
                    last_name = names[1] if len(names) > 1 else ""
                    user_id = row.get_attribute("data-user-id") or cells[0].get_attribute("data-user-id")  # Adjust attribute
                    cv_id = row.get_attribute("data-cv-id") or cells[0].get_attribute("data-cv-id")      # Adjust attribute
                    if user_id and cv_id:
                        cv_list.append({
                            "first_name": first_name,
                            "last_name": last_name,
                            "user_id": user_id,
                            "cv_id": cv_id,
                            "buyer_id": buyer_id
                        })
                        logger.debug(f"Found CV: {first_name} {last_name} (UserID: {user_id}, CvID: {cv_id})")
            except Exception as e:
                logger.warning(f"Error processing row: {str(e)}")
                continue

        return cv_list
    except Exception as e:
        logger.error(f"Failed to fetch CVs: {str(e)}")
        upload_screenshot(driver, config, "cv_list_failed")
        return []

def download_cv(config: Config, cv_data: Dict) -> Optional[Dict]:
    """Download a single CV using the API observed in the HAR file"""
    try:
        # Step 1: Get CV metadata
        params = {
            "buyerId": cv_data["buyer_id"],
            "CvId": cv_data["cv_id"],
            "UserId": cv_data["user_id"],
            "loggedInBuyer": cv_data["buyer_id"]
        }
        metadata_url = f"https://partnersapi.applygateway.com/api/Candidate/CandidateCombination?{urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        }
        response = requests.get(metadata_url, headers=headers)
        response.raise_for_status()
        metadata = response.json()
        
        if metadata.get("statusCode") != "2000":
            logger.error(f"Failed to get CV metadata for CvId {cv_data['cv_id']}: {metadata.get('message')}")
            return None
        
        file_name = metadata["data"]["fileName"]
        cv_file_name = metadata["data"]["cvFileName"]
        
        # Step 2: Download CV file
        download_url = f"https://cvfilemanager.applygateway.com/v1/cv/download?apiKey={config.api_key}&fileName={file_name}"
        response = requests.get(download_url, headers=headers)
        response.raise_for_status()
        
        return {
            "file_name": cv_file_name,
            "content": response.content,
            "first_name": cv_data["first_name"],
            "last_name": cv_data["last_name"],
            "user_id": cv_data["user_id"],
            "cv_id": cv_data["cv_id"]
        }
    except Exception as e:
        logger.error(f"Failed to download CV {cv_data['cv_id']}: {str(e)}")
        return None

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info("Starting CV download job")
        
        driver = setup_driver(config)
        
        # 1. Login flow
        if not perform_login(driver, config):
            logger.error("Login failed, cannot proceed")
            return 1
        logger.info("Login succeeded, proceeding with CV download")
        
        # 2. Get list of CVs from yesterday
        cv_list = get_yesterdays_cvs(driver, config)
        if not cv_list:
            logger.warning("No CVs found for yesterday")
            return 0
        
        # 3. Download and upload each CV
        for cv in cv_list:
            cv_data = download_cv(config, cv)
            if cv_data:
                yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")  # 20250701
                blob_name = f"cvs/{yesterday_date}/{cv_data['first_name']}-{cv_data['last_name']}-{cv_data['user_id']}-{cv_data['cv_id']}.pdf"
                if upload_file_to_gcs(config, cv_data["content"], blob_name):
                    logger.info(f"Successfully processed CV {cv_data['cv_id']}")
                else:
                    logger.error(f"Failed to upload CV {cv_data['cv_id']} to GCS")
        
        logger.info("CV download job completed successfully")
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
