import os
import time
import traceback
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import urlencode
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    username: str = os.getenv('HIRE_USERNAME', '')
    password: str = os.getenv('HIRE_PASSWORD', '')
    api_key: str = os.getenv('REACT_APP_CV_DOWNLOAD_API_KEY', '')
    headless: bool = os.getenv('HEADLESS', 'true').lower() == 'true'
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '120'))
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
    screenshot_bucket: str = os.getenv('DEBUG_SCREENSHOT_BUCKET', 'recruitment-engine-cvs-sp-260625')
    cv_bucket: str = os.getenv('CV_BUCKET', 'recruitment-engine-cvs-sp-260625')

    def validate(self):
        if not all([self.username, self.password, self.api_key]):
            raise ValueError("Missing credentials or API key in environment variables")
        if not os.path.exists(self.chrome_driver_path):
            raise FileNotFoundError(f"Chromedriver not found at {self.chrome_driver_path}")
        return self

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

def setup_driver(config: Config) -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    if config.headless:
        chrome_options.add_argument('--headless=new')
    service = Service(config.chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(10)
    return driver

def upload_screenshot(driver: webdriver.Chrome, config: Config, name: str) -> bool:
    try:
        time.sleep(5)
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
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(config.cv_bucket)
        blob = bucket.blob(blob_name)
        with BytesIO(file_content) as file_stream:
            blob.upload_from_file(file_stream, content_type='application/pdf')
        logger.info(f"Uploaded CV to GCS: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload CV to GCS: {str(e)}")
        return False

def perform_login(driver: webdriver.Chrome, config: Config) -> bool:
    """Robust login with retries and fallback selectors."""
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

        # Try different selectors for email
        email = None
        for _ in range(3):
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
                    time.sleep(2)

        email.send_keys(config.username)

        # Try different selectors for password
        password = None
        for _ in range(3):
            try:
                password = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
                break
            except:
                try:
                    password = driver.find_element(By.XPATH, "//input[@type='password']")
                    break
                except:
                    time.sleep(2)

        password.send_keys(config.password)

        # Try to find submit button
        submit = None
        for _ in range(3):
            try:
                submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                break
            except:
                try:
                    submit = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
                    break
                except:
                    time.sleep(2)

        submit.click()
        logger.debug("Clicked login button")

        # Wait for redirect
        WebDriverWait(driver, config.explicit_wait).until(
            EC.url_contains("clients.hireintelligence.io")
        )
        login_success = True
        logger.info("Login successful")
        time.sleep(5)
        upload_screenshot(driver, config, "login_success")
        return True

    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        upload_screenshot(driver, config, "login_failed")
        return False


def get_yesterdays_cvs(driver: webdriver.Chrome, config: Config, buyer_id: str = "1061"):
    cv_list = []
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_day = int(yesterday.strftime("%d"))

    try:
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        WebDriverWait(driver, config.explicit_wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(5)
        upload_screenshot(driver, config, "multi_candidate_admin")

        date_input = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".MuiInputBase-root input")))
        date_input.click()
        time.sleep(1)
        day_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'MuiPickersDay') and text()='{yesterday_day}']")))
        day_button.click()
        logger.info(f"Selected {yesterday_str} from calendar")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//table//tr[2]")))
        time.sleep(5)
        upload_screenshot(driver, config, "multi_candidate_admin_after_date_set")

        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        for row in rows[1:]:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 7:
                    continue
                candidate_text = cells[6].text.strip()
                names = candidate_text.split()[0:2]
                first_name = names[0] if len(names) > 0 else ""
                last_name = names[1] if len(names) > 1 else ""
                html = row.get_attribute("outerHTML")
                match = re.search(r"downloadCV\('(+)','(+)'\)", html)
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
            except Exception as e:
                logger.warning(f"Error processing row: {str(e)}")
        logger.info(f"✅ Found {len(cv_list)} CVs for {yesterday_str}")
        return cv_list
    except Exception as e:
        logger.error(f"Failed to fetch CVs: {str(e)}")
        upload_screenshot(driver, config, "cv_list_failed")
        return []

def download_cv(config: Config, cv_data: dict):
    try:
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
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(metadata_url, headers=headers)
        response.raise_for_status()
        metadata = response.json()
        if metadata.get("statusCode") != "2000":
            logger.error(f"Metadata fetch failed: {metadata.get('message')}")
            return None
        file_name = metadata["data"]["fileName"]
        cv_file_name = metadata["data"]["cvFileName"]
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
        logger.error(f"Failed to download CV: {str(e)}")
        return None

def main():
    driver = None
    try:
        config = Config().validate()
        logger.info("Starting CV download job")
        driver = setup_driver(config)
        if not perform_login(driver, config):
            logger.warning("Login failed")
            return 1
        driver.get("https://clients.hireintelligence.io/")
        WebDriverWait(driver, config.explicit_wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(5)
        upload_screenshot(driver, config, "dashboard")
        cv_list = get_yesterdays_cvs(driver, config)
        if not cv_list:
            logger.warning("No CVs found")
        else:
            current_date = datetime.now().strftime("%Y%m%d")
            for cv in cv_list:
                cv_data = download_cv(config, cv)
                if cv_data:
                    ext = cv_data['file_name'].split('.')[-1] if '.' in cv_data['file_name'] else 'pdf'
                    blob_name = f"cvs/{current_date}/{cv_data['first_name']}-{cv_data['last_name']}-{cv_data['user_id']}-{cv_data['cv_id']}.{ext}"
                    upload_file_to_gcs(config, cv_data["content"], blob_name)
        return 0
    except Exception as e:
        logger.error(f"Job failed: {str(e)}")
        logger.debug(traceback.format_exc())
        return 1
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser terminated")
            except Exception as e:
                logger.error(f"Error quitting browser: {str(e)}")

if __name__ == "__main__":
    exit(main())
