import os
import time
import signal
import subprocess
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
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
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '60'))  # Increased timeout
    output_dir: str = os.getenv('OUTPUT_DIR', 'output')
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

    # Console handler (recommended for Cloud Run logs)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

def setup_driver(config: Config) -> webdriver.Chrome:
    """Configure and initialize Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument(f'--window-size={config.screen_width},{config.screen_height}')
    chrome_options.add_argument('--page-load-strategy=eager')
    
    if config.headless:
        chrome_options.add_argument('--headless=new')

    service = Service(executable_path=config.chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(config.implicit_wait)
    return driver

def cleanup_driver(driver: webdriver.Chrome) -> None:
    """Properly cleanup WebDriver resources"""
    if driver:
        try:
            driver.quit()
            logger.info("Browser terminated gracefully")
        except Exception as e:
            logger.warning(f"Error during driver quit: {str(e)}")
            subprocess.run(["pkill", "-9", "-f", "chrome"], stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "-f", "chromedriver"], stderr=subprocess.DEVNULL)

def upload_to_gcs(bucket_name: str, image_data: bytes, destination_path: str) -> bool:
    """Upload screenshot to Google Cloud Storage"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        
        with BytesIO(image_data) as image_stream:
            blob.upload_from_file(image_stream, content_type='image/png')
        
        logger.info(f"Screenshot uploaded to gs://{bucket_name}/{destination_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {str(e)}")
        return False

def capture_screenshot(driver: webdriver.Chrome, description: str) -> bool:
    """Capture and upload screenshot with timestamp"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot = driver.get_screenshot_as_png()
        blob_name = f"screenshots/{description}_{timestamp}.png"
        
        return upload_to_gcs(config.screenshot_bucket, screenshot, blob_name)
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {str(e)}")
        return False

def perform_login(driver: webdriver.Chrome, config: Config) -> bool:
    """Perform login and capture screenshots before/after"""
    try:
        # 1. Navigate to login page and capture initial state
        driver.get("https://clients.hireintelligence.io/login")
        if not capture_screenshot(driver, "login_page"):
            logger.error("Failed to capture initial login page")
        
        # 2. Fill login form
        email_field = WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email'], input[type='email']"))
        )
        email_field.send_keys(config.username)
        
        password_field = driver.find_element(
            By.CSS_SELECTOR, "input[name='password'], input[type='password']"
        )
        password_field.send_keys(config.password)
        
        submit_button = driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
        )
        submit_button.click()
        
        # 3. Capture post-login state
        time.sleep(3)  # Wait for potential redirect
        if not capture_screenshot(driver, "post_login"):
            logger.error("Failed to capture post-login page")
        
        # 4. Verify successful login
        WebDriverWait(driver, config.explicit_wait).until(
            EC.url_contains("clients.hireintelligence.io")
        )
        return True
        
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        capture_screenshot(driver, "login_failure")
        return False

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info(f"Starting job with configuration: {config}")
        
        driver = setup_driver(config)
        
        # 1. Perform login flow with screenshots
        if not perform_login(driver, config):
            logger.error("Login process encountered issues - check screenshots")
        
        # 2. Capture dashboard page
        driver.get("https://clients.hireintelligence.io/")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Jobs Listed')]"))
        )
        capture_screenshot(driver, "dashboard")
        
        # 3. Capture multi-candidate admin page
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        time.sleep(3)  # Wait for page to load
        capture_screenshot(driver, "multi_candidate_admin")
        
        logger.info("Job completed successfully")
        return 0
        
    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        cleanup_driver(driver)

if __name__ == "__main__":
    exit(main())
