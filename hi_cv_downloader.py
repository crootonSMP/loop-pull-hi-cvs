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
    api_key: str = os.getenv('REACT_APP_CV_DOWNLOAD_API_KEY', '')  # Added for API access
    headless: bool = os.getenv('HEADLESS', 'true').lower() == 'true'
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '120'))  # Increased to 2 minutes
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
    screenshot_bucket: str = os.getenv('DEBUG_SCREENSHOT_BUCKET', 'recruitment-engine-cvs-sp-260625')
    cv_bucket: str = os.getenv('CV_BUCKET', 'recruitment-engine-cvs-sp-260625')  # Updated to match your bucket

    def validate(self):
        if not all([self.username, self.password, self.api_key]):
            raise ValueError("Missing credentials or API key in environment variables")
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

def upload_file_to_gcs(config: Config, file_content: bytes, blob_name: str) -> bool:
    """Upload CV file to GCS"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(config.cv_bucket)  # Uses recruitment-engine-cvs-sp-260625
        blob = bucket.blob(blob_name)
        with BytesIO(file_content) as file_stream:
            blob.upload_from_file(file_stream, content_type='application/pdf')
        logger.info(f"Uploaded CV to GCS: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload CV to GCS: {str(e)}")
        return False

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

def get_yesterdays_cvs(driver: webdriver.Chrome, config: Config, buyer_id: str = "1061") -> List[Dict]:
    from datetime import datetime, timedelta
    import re

    cv_list = []
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_day = int(yesterday.strftime("%d"))

    try:
        logger.info("Navigating to multi-candidate-admin to fetch yesterday's CVs")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        upload_screenshot(driver, config, "multi_candidate_admin")

        # Step 1: Click the date picker
        logger.debug("Opening date picker")
        date_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".MuiInputBase-root input"))
        )
        date_input.click()
        time.sleep(1)

        # Step 2: Click yesterday's day
        logger.debug(f"Clicking day {yesterday_day}")
        day_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'MuiPickersDay') and text()='{yesterday_day}']"))
        )
        day_button.click()
        logger.info(f"Selected date: {yesterday_str}")
        time.sleep(7)  # ⏳ Give UI time to refresh table

        # Step 3: Wait for table to load
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tr"))
        )
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")

        for row in rows[1:]:  # skip header
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 7:
                    continue

                candidate_text = cells[6].text.strip()
                names = candidate_text.split()[0:2]
                first_name = names[0] if len(names) > 0 else ""
                last_name = names[1] if len(names) > 1 else ""

                # Fallback: pull IDs from raw row HTML
                html = row.get_attribute("outerHTML")
                match = re.search(r"downloadCV\('(\d+)',\s*'(\d+)'\)", html)
                if match:
                    user_id, cv_id = match.groups()
                    cv_list.append({
                        "first_name": first_name,
                        "last_name": last_name,
                        "user_id": user_id,
                        "cv_id": cv_id,
                        "buyer_id": buyer_id
                    })
                    logger.debug(f"✅ Found CV: {first_name} {last_name} (UserID: {user_id}, CvID: {cv_id})")
                else:
                    logger.warning("❌ Could not extract IDs from row HTML")
            except Exception as e:
                logger.warning(f"Error processing row: {str(e)}")
                continue

        logger.info(f"Finished scanning table. Found {len(cv_list)} CV(s) for {yesterday_str}")
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
        
        if not perform_login(driver, config):
            logger.warning("Login attempt failed, but proceeding with navigation - check screenshots")
        else:
            logger.info("Login succeeded, proceeding with navigation")
        
        driver.get("https://clients.hireintelligence.io/")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        upload_screenshot(driver, config, "dashboard")

        try:
            driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
            WebDriverWait(driver, config.explicit_wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            upload_screenshot(driver, config, "multi_candidate_admin")

            cv_list = get_yesterdays_cvs(driver, config)
            if not cv_list:
                logger.warning("No CVs found on the page")
            else:
                current_date = datetime.now().strftime("%Y%m%d")
                for cv in cv_list:
                    cv_data = download_cv(config, cv)
                    if cv_data:
                        # extract extension
                        ext = cv_data['file_name'].split('.')[-1] if '.' in cv_data['file_name'] else 'pdf'
                        blob_name = f"cvs/{current_date}/{cv_data['first_name']}-{cv_data['last_name']}-{cv_data['user_id']}-{cv_data['cv_id']}.{ext}"
                        if upload_file_to_gcs(config, cv_data["content"], blob_name):
                            logger.info(f"Successfully processed CV {cv_data['cv_id']}")
                        else:
                            logger.error(f"Failed to upload CV {cv_data['cv_id']} to GCS")
        except Exception as e:
            logger.error(f"Failed to navigate to multi-candidate-admin or process CVs: {str(e)}")
            upload_screenshot(driver, config, "multi_candidate_admin_failed")

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
