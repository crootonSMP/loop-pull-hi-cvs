import os
import time
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import logging
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException, 
                                      WebDriverException,
                                      TimeoutException)
from dotenv import load_dotenv
import pandas as pd
import signal
from contextlib import contextmanager

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

def verify_chrome_installation(config: Config) -> Tuple[bool, str]:
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
            chrome_options.add_argument('--remote-debugging-port=9222')
            
            # Headless configuration
            if config.headless:
                chrome_options.add_argument('--headless=new')
            
            # Configure service with error handling
            service = Service(
                executable_path=config.chrome_driver_path,
                service_args=['--verbose']
            )
            
            # Additional stability parameters
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options,
                service_log_path=os.path.join(config.output_dir, 'chromedriver.log')
            )
            
            # Basic verification
            driver.get('about:blank')
            if not driver.title == '':
                raise RuntimeError("Driver verification failed")
                
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

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info("Starting scraping job with configuration: %s", config)
        
        driver = setup_driver(config)
        
        # Your main scraping logic would go here
        # login_to_hireintelligence(driver, config)
        # result = extract_data_from_retool(driver, config)
        
        logger.info("Job completed successfully")
        return 0
        
    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        cleanup_driver(driver)

if __name__ == "__main__":
    exit(main())
