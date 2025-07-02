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

# [Keep your existing Config class and setup_logging function...]

def upload_to_gcs(bucket_name: str, image_data: bytes, destination_path: str) -> None:
    """Upload screenshot to Google Cloud Storage"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    
    with BytesIO(image_data) as image_stream:
        blob.upload_from_file(image_stream, content_type='image/png')
    
    logger.info(f"Screenshot uploaded to gs://{bucket_name}/{destination_path}")

def capture_screenshot(driver: webdriver.Chrome, url: str, description: str) -> bytes:
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

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info(f"Starting job with configuration: {config}")
        
        driver = setup_driver(config)
        bucket_name = "recruitment-engine-cvs-sp-260625"
        
        # List of URLs and their descriptions
        pages = [
            ("https://clients.hireintelligence.io/login", "jobs_dashboard"),
            ("https://clients.hireintelligence.io/multi-candidate-admin", "multi_candidate_admin")
        ]
        
        for url, description in pages:
            try:
                screenshot = capture_screenshot(driver, url, description)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{description}_{timestamp}_{uuid.uuid4().hex[:6]}.png"
                upload_to_gcs(bucket_name, screenshot, f"screenshots/{filename}")
            except Exception as e:
                logger.error(f"Failed processing {url}: {str(e)}")
                continue
        
        logger.info("Screenshot capture completed")
        return 0
        
    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        if driver:
            cleanup_driver(driver)

if __name__ == "__main__":
    exit(main())
