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
from PIL import Image

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
    output_dir: str = os.getenv('OUTPUT_DIR', 'output')
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
    screen_width: int = int(os.getenv('SCREEN_WIDTH', '1920'))
    screen_height: int = int(os.getenv('SCREEN_HEIGHT', '1080'))
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    retry_delay: int = int(os.getenv('RETRY_DELAY', '5'))

    def validate(self):
        """Validate configuration and credentials"""
        if not self.username or not self.password:
            raise ValueError("Missing credentials in environment variables")
        os.makedirs(self.output_dir, exist_ok=True)
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
    
    # File handler with rotation
    file_handler = logging.FileHandler('scraper.log')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def upload_to_gcs(bucket_name: str, image_data: bytes, destination_path: str) -> None:
    """Upload screenshot to Google Cloud Storage"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        
        with BytesIO(image_data) as image_stream:
            blob.upload_from_file(image_stream, content_type='image/png')
        
        logger.info(f"Screenshot uploaded to gs://{bucket_name}/{destination_path}")
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {str(e)}")
        raise

def capture_screenshot(driver: webdriver.Chrome, url: str) -> bytes:
    """Navigate to URL and capture screenshot"""
    try:
        logger.info(f"Navigating to {url}")
        driver.get(url)
        
        # Handle login if needed
        if "login" in url:
            logger.info("Performing login...")
            WebDriverWait(driver, config.explicit_wait).until(
                EC.presence_of_element_located((By.NAME, "email"))
            ).send_keys(config.username)
            
            driver.find_element(By.NAME, "password").send_keys(config.password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(3)  # Wait for login
        
        # Wait for jobs count on dashboard
        if url.rstrip('/') == "https://clients.hireintelligence.io":
            WebDriverWait(driver, config.explicit_wait).until(
                EC.text_to_be_present_in_element(
                    (By.XPATH, "//*[contains(text(), 'Jobs Listed')]"),
                    "Jobs Listed"
                )
            )
        
        return driver.get_screenshot_as_png()
        
    except Exception as e:
        logger.error(f"Failed to capture {url}: {str(e)}")
        raise

def setup_driver(config: Config) -> webdriver.Chrome:
    """Configure and initialize Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument(f'--window-size={config.screen_width},{config.screen_height}')
    
    if config.headless:
        chrome_options.add_argument('--headless=new')
    
    service = Service(executable_path=config.chrome_driver_path)
    return webdriver.Chrome(service=service, options=chrome_options)

def cleanup_driver(driver: webdriver.Chrome) -> None:
    """Properly cleanup WebDriver resources"""
    if driver:
        try:
            driver.quit()
            logger.info("Browser terminated gracefully")
        except Exception as e:
            logger.warning(f"Error during driver quit: {str(e)}")

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        bucket_name = "recruitment-engine-cvs-sp-260625"
        
        driver = setup_driver(config)
        
        # List of URLs to capture
        urls = [
            "https://clients.hireintelligence.io/login",
            "https://clients.hireintelligence.io/multi-candidate-admin"
        ]
        
        for url in urls:
            try:
                screenshot = capture_screenshot(driver, url)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                description = "login" if "login" in url else "candidate_admin"
                filename = f"{description}_{timestamp}.png"
                upload_to_gcs(bucket_name, screenshot, f"screenshots/{filename}")
            except Exception as e:
                logger.error(f"Skipping {url} due to error: {str(e)}")
                continue
        
        return 0
    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        cleanup_driver(driver)

if __name__ == "__main__":
    exit(main())
