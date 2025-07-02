import os
import time
import logging
import requests
from io import BytesIO
from datetime import datetime

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
from google.cloud import secretmanager
import google.auth

# Load environment variables
from dotenv import load_dotenv

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global driver for cookie access
driver = None

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

def setup_driver() -> webdriver.Chrome:
    """Initialize WebDriver with enhanced options"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--headless=new')
    
    service = Service(
        executable_path="/usr/local/bin/chromedriver",
        service_args=['--verbose', '--log-path=/tmp/chromedriver.log']
    )
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        logger.error(f"Driver initialization failed: {str(e)}")
        raise

def upload_screenshot(name: str) -> bool:
    """Capture and upload screenshot with error handling"""
    global driver
    try:
        screenshot = driver.get_screenshot_as_png()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"screenshots/{name}_{timestamp}.png"
        
        bucket = storage_client.bucket("recruitment-engine-cvs-sp-260625")
        blob = bucket.blob(blob_name)
        
        with BytesIO(screenshot) as image_stream:
            blob.upload_from_file(image_stream, content_type='image/png')
        
        logger.info(f"Uploaded screenshot: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {str(e)}")
        return False

def perform_login() -> bool:
    """Perform login using Selenium"""
    global driver
    username = os.getenv('HIRE_USERNAME', '')
    password = get_secret("HIRE_PASSWORD")
    
    login_success = False
    try:
        driver.get("https://clients.hireintelligence.io/login")
        time.sleep(2)
        logger.info("Navigated to login page")
        upload_screenshot("login_page")

        WebDriverWait(driver, 120).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        logger.debug("Login form detected")

        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))
        )
        email.send_keys(username)
        logger.debug("Entered username")

        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        password_field.send_keys(password)
        logger.debug("Entered password")

        submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit.click()
        logger.debug("Clicked submit button")

        WebDriverWait(driver, 120).until(
            EC.url_contains("clients.hireintelligence.io")
        )
        login_success = True
        logger.info("Login successful")
        upload_screenshot("login_success")
        return True

    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        upload_screenshot("login_failed")
        return False
    finally:
        if login_success:
            return True
        return False

def upload_file_to_gcs(file_content: BytesIO, destination_blob_name: str) -> bool:
    """Upload a file (e.g., CV) to GCS"""
    try:
        bucket = storage_client.bucket("recruitment-engine-cvs-sp-260625")
        blob = bucket.blob(destination_blob_name)
        file_content.seek(0)
        blob.upload_from_file(file_content, content_type='application/pdf')
        logger.info(f"Uploaded file to: gs://recruitment-engine-cvs-sp-260625/{destination_blob_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        return False

def download_cv(cv_id: int) -> tuple[str, BytesIO]:
    """Download a CV using the API with Selenium cookies"""
    api_key = get_secret("cv-download-api-key")
    
    # Step 1: Fetch CV metadata with Selenium cookies
    metadata_url = "https://partnersapi.applygateway.com/api/Candidate/CandidateCombination"
    params = {
        "buyerId": "1061",
        "CvId": cv_id,
        "UserId": "5414048",
        "loggedInBuyer": "1061"
    }
    try:
        global driver
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

def get_top_cv_id() -> Optional[int]:
    """Extract the CV ID from the first row of the multi-candidate-admin table"""
    global driver
    try:
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        WebDriverWait(driver, 120).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        upload_screenshot("multi_candidate_admin")
        logger.info("Captured multi-candidate-admin page")

        # Assume the table has a column with CV ID (adjust selector based on page structure)
        first_row = driver.find_element(By.CSS_SELECTOR, "table tbody tr:first-child")
        cv_id_element = first_row.find_element(By.CSS_SELECTOR, "[data-cv-id], [id*=cv], td:nth-child(2)")  # Adjust selector
        cv_id = int(cv_id_element.text.strip())
        logger.info(f"Extracted top CV ID: {cv_id}")
        return cv_id
    except Exception as e:
        logger.error(f"Failed to extract top CV ID: {str(e)}")
        upload_screenshot("multi_candidate_admin_failed")
        return None

def main():
    load_dotenv()  # Load environment variables
    global driver
    driver = setup_driver()
    
    if not perform_login():
        logger.error("Login failed, exiting job")
        driver.quit()
        return 1
    
    cv_id = get_top_cv_id()
    if cv_id is None:
        logger.error("Failed to get top CV ID, exiting job")
        driver.quit()
        return 1
    
    bucket_name = "recruitment-engine-cvs-sp-260625"
    cv_ids = [cv_id]  # Use the top CV ID

    for cv_id in cv_ids:
        cv_file_name, file_content = download_cv(cv_id)
        if cv_file_name and file_content:
            destination_blob_name = f"cvs/{cv_file_name}"
            if upload_file_to_gcs(file_content, destination_blob_name):
                logger.info(f"Successfully processed CV {cv_id}")
            time.sleep(1)  # Respect server load with 1-second delay

    logger.info("Job completed")
    driver.quit()
    return 0

if __name__ == "__main__":
    exit(main())
