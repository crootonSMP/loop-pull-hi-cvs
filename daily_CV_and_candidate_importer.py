import os
import time
import pandas as pd
from datetime import datetime
import logging
import subprocess
# --- Main Libraries ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from google.cloud import storage

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Script entry point reached")

# --- Environment Variables ---
USERNAME = os.getenv("HIRE_USERNAME")
PASSWORD = os.getenv("HIRE_PASSWORD")
LOGIN_URL = "https://clients.hireintelligence.io/"
CANDIDATE_URL = "https://clients.hireintelligence.io/candidates"
BUCKET_NAME = os.getenv("CV_BUCKET_NAME", "intelligent-recruitment-cvs")
# --- Bright Data Credentials ---
BRIGHTDATA_USERNAME = os.getenv("BRIGHTDATA_USERNAME")
BRIGHTDATA_PASSWORD = os.getenv("BRIGHTDATA_PASSWORD")
BRIGHTDATA_HOST = "brd.superproxy.io"
BRIGHTDATA_PORT = 22225

def start_browser():
    logging.info("Entering start_browser")
    driver_path = "/usr/local/bin/chromedriver"
    logging.info(f"Checking ChromeDriver at: {driver_path}")
    if not os.path.exists(driver_path):
        logging.error(f"ChromeDriver not found at {driver_path}")
        raise FileNotFoundError(f"ChromeDriver missing: {driver_path}")
    
    # Check Chrome version
    try:
        chrome_version = subprocess.check_output(["google-chrome", "--version"]).decode()
        logging.info(f"Chrome version: {chrome_version}")
    except Exception as e:
        logging.error(f"Failed to get Chrome version: {e}")
    
    options = webdriver.ChromeOptions()
    proxy_url = f"http://{BRIGHTDATA_USERNAME}:{BRIGHTDATA_PASSWORD}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}"
    logging.info("Applying proxy settings")
    # Comment out proxy to test without it
    # options.add_argument(f'--proxy-server={proxy_url}')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--window-size=1280,720')
    
    logging.info("Starting ChromeDriver service")
    service = Service(executable_path=driver_path)
    logging.info("Initializing WebDriver")
    driver = webdriver.Chrome(service=service, options=options)
    logging.info("Browser started successfully")
    return driver

def login(driver):
    logging.info("Navigating to login page...")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 60)
    
    try:
        wait.until(EC.presence_of_element_located((By.ID, "email")))
        logging.info("Page loaded. Simulating login...")
        email_input = driver.find_element(By.ID, "email")
        password_input = driver.find_element(By.ID, "password")
        login_button = driver.find_element(By.XPATH, '//button[contains(text(), "Login")]')
        
        actions = ActionChains(driver)
        actions.move_to_element(email_input).pause(0.6).click().send_keys(USERNAME).pause(0.4)
        actions.move_to_element(password_input).pause(0.7).click().send_keys(PASSWORD).pause(0.5)
        actions.move_to_element(login_button).click()
        actions.perform()
    except Exception as e:
        logging.error(f"Login error: {e}", exc_info=True)
        try:
            driver.save_screenshot("login_error_screenshot.png")
            logging.info("Screenshot saved: login_error_screenshot.png")
        except Exception as ss_e:
            logging.error(f"Screenshot failed: {ss_e}")
        raise
    
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Jobs Listed")]')))
    logging.info("Logged in successfully")

def fetch_candidates(driver):
    logging.info("Navigating to candidates page...")
    driver.get(CANDIDATE_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
    logging.info(f"Found {len(rows)} candidate rows")
    data = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 4:
            data.append({
                "name": cols[0].text.strip(),
                "email": cols[1].text.strip(),
                "job_ref_number": cols[2].text.strip(),
                "created_on": cols[3].text.strip()
            })
    return pd.DataFrame(data)

def save_and_upload(df):
    if df.empty:
        logging.warning("No candidate data found")
        return
    filename = f"hi_candidates_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    df.to_excel(filename, index=False)
    logging.info(f"Saved report: {filename}")
    logging.info("Uploading to Google Cloud Storage...")
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"reports/{filename}")
    blob.upload_from_filename(filename)
    logging.info(f"Uploaded to: gs://{BUCKET_NAME}/reports/{filename}")

def main():
    logging.info("Starting main function")
    driver = None
    try:
        driver = start_browser()
        login(driver)
        df = fetch_candidates(driver)
        save_and_upload(df)
    except Exception as e:
        logging.critical(f"Critical error in main: {e}", exc_info=True)
    finally:
        if driver:
            logging.info("Closing browser session")
            driver.quit()
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(os.getenv("CV_BUCKET_NAME", "intelligent-recruitment-cvs"))
            blob = bucket.blob("logs/entrypoint.log")
            blob.upload_from_filename("/tmp/entrypoint.log")
            logging.info("Uploaded entrypoint.log to GCS")
        except Exception as e:
            logging.error(f"Failed to upload entrypoint.log: {e}")
        logging.info("Script finished")

if __name__ == "__main__":
    main()
