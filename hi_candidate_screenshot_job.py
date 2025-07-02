import os
import time
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
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Configuration
@dataclass
@dataclass
class Config:
    username: str = os.getenv('HIRE_USERNAME', '')
    password: str = os.getenv('HIRE_PASSWORD', '')  # This will come from the secret
    headless: bool = os.getenv('HEADLESS', 'true').lower() == 'true'
    implicit_wait: int = int(os.getenv('IMPLICIT_WAIT', '10'))
    explicit_wait: int = int(os.getenv('EXPLICIT_WAIT', '20'))
    output_dir: str = os.getenv('OUTPUT_DIR', 'output')
    chrome_driver_path: str = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')

    def validate(self):
        if not self.username or not self.password:
            raise ValueError("Missing credentials in environment variables")
        return self

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_driver(config: Config) -> webdriver.Chrome:
    """Configure and initialize Chrome WebDriver with robust options"""
    chrome_options = Options()
    
    # Core configuration
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # New headless mode
    if config.headless:
        chrome_options.add_argument('--headless=new')
    
    # Anti-detection and optimization
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Configure service with logging
    service = Service(
        executable_path=config.chrome_driver_path,
        service_args=['--verbose'],
        log_output='chromedriver.log'
    )
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(config.implicit_wait)
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Driver initialization failed: {str(e)}")
        raise

def login_to_hireintelligence(driver: webdriver.Chrome, config: Config) -> None:
    """Handle login to the HireIntelligence Retool application"""
    logger.info("Navigating to login page")
    driver.get("https://clients.hireintelligence.io/login")
    
    # Wait for page to load completely
    WebDriverWait(driver, config.explicit_wait).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    
    # Find all iframes and attempt login in each
    iframes = WebDriverWait(driver, config.explicit_wait).until(
        EC.presence_of_all_elements_located((By.TAG_NAME, "iframe"))
    )
    
    if not iframes:
        logger.error("No iframes detected on login page")
        raise RuntimeError("Login iframe not found")
        
    for idx, iframe in enumerate(iframes, 1):
        try:
            logger.info(f"Attempting login with iframe {idx}/{len(iframes)}")
            driver.switch_to.frame(iframe)
            
            # Enhanced element detection with multiple selector options
            email_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((
                    By.CSS_SELECTOR, 
                    "input[name='email'], input[type='email'], #email"
                ))
            )
            email_field.clear()
            email_field.send_keys(config.username)
            
            password_field = driver.find_element(
                By.CSS_SELECTOR, 
                "input[name='password'], input[type='password'], #password"
            )
            password_field.clear()
            password_field.send_keys(config.password)
            
            submit_button = driver.find_element(
                By.CSS_SELECTOR, 
                "button[type='submit'], button:contains('Log in'), #login-button"
            )
            submit_button.click()
            
            # Verify successful login by waiting for password field to disappear
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            
            logger.info("Login successful")
            driver.switch_to.default_content()
            return
            
        except Exception as e:
            logger.warning(f"Login attempt {idx} failed: {str(e)}")
            driver.switch_to.default_content()
            continue
            
    raise RuntimeError("Failed to login through any iframe")

def extract_data_from_retool(driver: webdriver.Chrome, config: Config) -> pd.DataFrame:
    """Extract and save data from Retool application"""
    logger.info("Starting data extraction process")
    
    # Wait for main application iframe
    main_iframe = WebDriverWait(driver, config.explicit_wait).until(
        EC.presence_of_element_located((
            By.CSS_SELECTOR, 
            "iframe[src*='retool'], iframe[src*='app'], iframe#main-iframe"
        ))
    )
    driver.switch_to.frame(main_iframe)
    logger.info("Switched to main application iframe")
    
    # Wait for loading to complete
    WebDriverWait(driver, config.explicit_wait).until(
        EC.invisibility_of_element_located((
            By.CSS_SELECTOR, 
            ".loading-spinner, .progress-bar, .ant-spin"
        ))
    )
    
    try:
        # Wait for data grid to appear
        WebDriverWait(driver, config.explicit_wait).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, 
                ".retool-data-grid, .ag-grid, .data-table, .ant-table"
            ))
        )
        
        # Get column headers
        headers = [
            th.text for th in driver.find_elements(
                By.CSS_SELECTOR, 
                ".retool-data-grid thead th, .ag-header-cell-text, .ant-table-thead th"
            )
        ]
        
        data = []
        page = 1
        max_pages = 10  # Safety limit
        
        while page <= max_pages:
            logger.info(f"Processing page {page}")
            
            # Get all visible rows
            rows = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    ".retool-data-grid tbody tr, .ag-row, .ant-table-row"
                ))
            )
            
            # Extract data from each row
            for row in rows:
                cells = row.find_elements(By.CSS_SELECTOR, "td, .ag-cell, .ant-table-cell")
                if len(cells) == len(headers):
                    row_data = {headers[i]: cell.text for i, cell in enumerate(cells)}
                    data.append(row_data)
            
            # Handle pagination
            try:
                next_button = driver.find_element(
                    By.CSS_SELECTOR,
                    ".next-page, .ag-paging-next, .ant-pagination-next"
                )
                if "disabled" in next_button.get_attribute("class"):
                    break
                
                next_button.click()
                time.sleep(2)  # Allow new page to load
                page += 1
            except:
                break
        
        # Create DataFrame
        df = pd.DataFrame(data)
        logger.info(f"Extracted {len(df)} records from {page-1} pages")
        
        # Save with timestamp
        os.makedirs(config.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config.output_dir, f"hireintelligence_export_{timestamp}.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"Data saved to {output_path}")
        
        return df
        
    except Exception as e:
        logger.error(f"Data extraction failed: {str(e)}")
        driver.save_screenshot("data_extraction_error.png")
        raise
    finally:
        driver.switch_to.default_content()

def main() -> int:
    """Main execution function with proper error handling"""
    try:
        config = Config().validate()  # This will validate credentials
        
        logger.info("Starting HireIntelligence scraper")
        driver = setup_driver(config)
        
        login_to_hireintelligence(driver, config)
        extract_data_from_retool(driver, config)
        
        logger.info("Scraping completed successfully")
        return 0
        
    except Exception as e:
        logger.critical(f"Script failed: {str(e)}", exc_info=True)
        return 1
    finally:
        if 'driver' in locals():
            driver.quit()
            logger.info("Browser terminated")

        
    except Exception as e:
        logger.critical(f"Script failed: {str(e)}", exc_info=True)
        return 1
    finally:
        if 'driver' in locals():
            driver.quit()
            logger.info("Browser terminated")

if __name__ == "__main__":
    exit(main())
