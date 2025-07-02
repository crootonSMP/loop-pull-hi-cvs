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
from dotenv import load_dotenv

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

def perform_login(driver: webdriver.Chrome, config: Config) -> bool:
    """Simplified login flow with screenshots and dynamic element handling"""
    try:
        # Step 1: Navigate to login page
        driver.get("https://clients.hireintelligence.io/login")
        time.sleep(2)
        logger.info("Navigated to login page")
        upload_screenshot(driver, config, "login_page")

        # Step 2: Wait for the form to load (using a more reliable parent container)
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        logger.debug("Login form detected")

        # Step 3: Find email field with updated selector
        # Inspect the page to confirm the selector; fallback to alternative selectors
        try:
            email = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))
            )
        except:
            # Fallback selectors based on common patterns
            try:
                email = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
            except:
                email = driver.find_element(By.XPATH, "//input[contains(@id, 'email')]")
        
        email.send_keys(config.username)
        logger.debug("Entered username")

        # Step 4: Find password field
        try:
            password = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        except:
            password = driver.find_element(By.XPATH, "//input[@type='password']")
        password.send_keys(config.password)
        logger.debug("Entered password")

        # Step 5: Submit form
        try:
            submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except:
            submit = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        submit.click()
        logger.debug("Clicked submit button")

        # Step 6: Verify login success
        WebDriverWait(driver, config.explicit_wait).until(
            EC.url_contains("clients.hireintelligence.io")
        )
        logger.info("Login successful")
        upload_screenshot(driver, config, "login_success")
        return True

    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        logger.debug(f"Page source:\n{driver.page_source[:1000]}...")  # Truncate for brevity
        logger.debug(f"Stack trace:\n{traceback.format_exc()}")
        upload_screenshot(driver, config, "login_failed")
        return False

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info("Starting screenshot capture job")
        
        driver = setup_driver(config)
        
        # 1. Login flow
        if not perform_login(driver, config):
            raise RuntimeError("Login failed - check screenshots")
        
        # 2. Capture dashboard
        driver.get("https://clients.hireintelligence.io/")
        upload_screenshot(driver, config, "dashboard")
        
        # 3. Capture admin page
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        upload_screenshot(driver, config, "multi_candidate_admin")
        
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
