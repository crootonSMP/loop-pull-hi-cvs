import os
import time
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException  # ✅ FIXED
from dotenv import load_dotenv
import pandas as pd

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

    def validate(self):
        """Validate configuration and credentials"""
        if not self.username or not self.password:
            raise ValueError("Missing credentials in environment variables")
        os.makedirs(self.output_dir, exist_ok=True)
        return self

# Initialize logging
def setup_logging():
    """Configure logging with file rotation"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler
    file_handler = logging.FileHandler('scraper.log')
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def verify_chrome_installation() -> bool:
    """Verify Chrome and Chromedriver are properly installed"""
    try:
        chrome_version = subprocess.run(
            ["google-chrome", "--version"],
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        
        driver_version = subprocess.run(
            ["chromedriver", "--version"],
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        
        logger.info(f"Chrome version: {chrome_version}")
        logger.info(f"Chromedriver version: {driver_version}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Chrome verification failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected verification error: {str(e)}")
        return False

def setup_driver(config: Config) -> webdriver.Chrome:
    """Configure and initialize Chrome WebDriver with robust options"""
    if not verify_chrome_installation():
        raise RuntimeError("Chrome/Chromedriver verification failed")
    
    chrome_options = Options()
    
    # Essential configuration
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument(f'--window-size={config.screen_width},{config.screen_height}')
    chrome_options.add_argument('--user-data-dir=/tmp/chrome-profile')
    chrome_options.add_argument('--disable-application-cache')
    
    # Headless configuration
    if config.headless:
        chrome_options.add_argument('--headless=new')
    
    # Stability and anti-detection
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Configure service with logging
    service = Service(
        executable_path=config.chrome_driver_path,
        service_args=['--verbose'],
        log_path='chromedriver.log'
    )
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_window_size(config.screen_width, config.screen_height)
        driver.implicitly_wait(config.implicit_wait)
        logger.info("WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Driver initialization failed: {str(e)}")
        raise RuntimeError("Failed to initialize WebDriver") from e

def login_to_hireintelligence(driver: webdriver.Chrome, config: Config) -> None:
    """Handle login to the HireIntelligence application"""
    logger.info("Starting login process")
    
    try:
        driver.get("https://clients.hireintelligence.io/login")
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )  # ✅ FIXED: closing parenthesis
        
        iframes = WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))
        
        if not iframes:
            raise RuntimeError("No login iframes found")
            
        for idx, iframe in enumerate(iframes, 1):
            try:
                logger.info(f"Attempting login with iframe {idx}")
                driver.switch_to.frame(iframe)
                
                # Unified element location strategy
                def find_with_fallback(*selectors):
                    for selector in selectors:
                        try:
                            return driver.find_element(By.CSS_SELECTOR, selector)
                        except:
                            continue
                    raise NoSuchElementException("No matching elements found")  # ✅ FIXED
                
                email_field = find_with_fallback(
                    "input[name='email']",
                    "input[type='email']",
                    "#email"
                )
                email_field.clear()
                email_field.send_keys(config.username)
                
                password_field = find_with_fallback(
                    "input[name='password']",
                    "input[type='password']",
                    "#password"
                )
                password_field.clear()
                password_field.send_keys(config.password)
                
                submit_button = find_with_fallback(
                    "button[type='submit']",
                    "button[id*='login']",
                    "#login-button"
                )
                submit_button.click()
                
                # Verify login success
                WebDriverWait(driver, 10).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
                logger.info("Login successful")
                driver.switch_to.default_content()
                return
                
            except Exception as e:
                logger.warning(f"Login attempt {idx} failed: {str(e)}")
                driver.switch_to.default_content()
                continue
                
        raise RuntimeError("All login attempts failed")
        
    except Exception as e:
        logger.error(f"Login process failed: {str(e)}")
        driver.save_screenshot("login_error.png")
        raise

def extract_data_from_retool(driver: webdriver.Chrome, config: Config) -> pd.DataFrame:
    """Extract and save data from Retool application"""
    logger.info("Starting data extraction")
    
    try:
        # Switch to main application iframe
        main_iframe = WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='retool'], iframe[src*='app']"))
        )
        driver.switch_to.frame(main_iframe)
        
        # Wait for data grid to load
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".retool-data-grid, .ag-grid, .ant-table"))
        )
        
        headers = [th.text for th in driver.find_elements(
            By.CSS_SELECTOR, ".retool-data-grid thead th, .ag-header-cell-text, .ant-table-thead th")]
        
        data = []
        page = 1
        max_pages = 10
        
        while page <= max_pages:
            logger.info(f"Processing page {page}")
            
            rows = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR, ".retool-data-grid tbody tr, .ag-row, .ant-table-row"))
            )
            
            for row in rows:
                cells = row.find_elements(By.CSS_SELECTOR, "td, .ag-cell, .ant-table-cell")
                if len(cells) == len(headers):
                    data.append({headers[i]: cell.text for i, cell in enumerate(cells)})
            
            try:
                next_button = driver.find_element(
                    By.CSS_SELECTOR, ".next-page, .ag-paging-next, .ant-pagination-next")
                if "disabled" in next_button.get_attribute("class"):
                    break
                next_button.click()
                WebDriverWait(driver, 10).until(EC.staleness_of(next_button))
                page += 1
            except:
                break
        
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config.output_dir, f"hireintelligence_export_{timestamp}.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(df)} records to {output_path}")
        return df
        
    except Exception as e:
        logger.error(f"Data extraction failed: {str(e)}")
        driver.save_screenshot("extraction_error.png")
        raise
    finally:
        driver.switch_to.default_content()

def main() -> int:
    """Main execution function with proper error handling"""
    driver = None
    try:
        config = Config().validate()
        logger.info("Starting scraping job")
        
        driver = setup_driver(config)
        login_to_hireintelligence(driver, config)
        result = extract_data_from_retool(driver, config)
        
        logger.info("Job completed successfully")
        return 0
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return 1
    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser terminated")
            except Exception as e:
                logger.warning(f"Error during driver quit: {str(e)}")
            subprocess.run(["pkill", "-f", "chrome"], stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    exit(main())
