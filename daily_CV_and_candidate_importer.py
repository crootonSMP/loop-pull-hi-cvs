import os
import time
import pandas as pd
from datetime import datetime
from google.cloud import storage
import logging

# ✅ IMPORT VANILLA SELENIUM
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables ---
USERNAME = os.getenv("HIRE_USERNAME")
PASSWORD = os.getenv("HIRE_PASSWORD")
LOGIN_URL = "https://clients.hireintelligence.io/"
CANDIDATE_URL = "https://clients.hireintelligence.io/candidates"
BUCKET_NAME = os.getenv("CV_BUCKET_NAME", "intelligent-recruitment-cvs")

def start_browser():
    logging.info("🚀 Launching Chrome browser in a virtual display (headed mode)...")
    
    options = webdriver.ChromeOptions()
    
    # All our best evasion options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--disable-webgl')
    options.add_argument('--window-size=1280,720')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")
    options.add_argument('accept-language=en-US,en;q=0.9')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver_path = "/usr/local/bin/chromedriver"
    service = Service(executable_path=driver_path)

    logging.info("Initializing webdriver.Chrome()...")
    driver = webdriver.Chrome(service=service, options=options)
    logging.info("✅ Browser started successfully!")
    return driver

def login(driver):
    logging.info("🔐 Navigating to login page...")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)
    try:
        wait.until(EC.presence_of_element_located((By.ID, "email")))
        logging.info("⏳ Pausing to allow bot detection scripts to run...")
        time.sleep(5) # Increased sleep time for maximum safety
        
        email_input = driver.find_element(By.ID, "email")
        password_input = driver.find_element(By.ID, "password")
        login_button = driver.find_element(By.XPATH, '//button[contains(text(), "Login")]')
        
        logging.info("📝 Simulating user actions and submitting login form...")
        actions = ActionChains(driver)
        actions.move_to_element(email_input).pause(0.5).click().send_keys(USERNAME).pause(0.5)
        actions.move_to_element(password_input).pause(0.5).click().send_keys(PASSWORD).pause(0.5)
        actions.move_to_element(login_button).click()
        actions.perform()
    except Exception as e:
        logging.error(f"❌ An error occurred during the login process: {e}", exc_info=True)
        # Taking a screenshot is very helpful for debugging login failures
        try:
            driver.save_screenshot("login_error_screenshot.png")
            logging.info("📸 Screenshot saved as login_error_screenshot.png")
        except Exception as ss_e:
            logging.error(f"Could not save screenshot: {ss_e}")
        raise
        
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Jobs Listed")]')))
    logging.info("✅ Logged in successfully.")


def fetch_candidates(driver):
    logging.info("📥 Navigating to candidates page...")
    driver.get(CANDIDATE_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
    logging.info(f"📄 Found {len(rows)} candidate rows.")
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
        logging.warning("⚠️ No candidate data found to save.")
        return
    filename = f"hi_candidates_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    df.to_excel(filename, index=False)
    logging.info(f"💾 Report saved locally as {filename}")
    logging.info("☁️ Uploading report to Google Cloud Storage...")
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"reports/{filename}")
    blob.upload_from_filename(filename)
    logging.info(f"✅ Uploaded to: gs://{BUCKET_NAME}/reports/{filename}")


def main():
    logging.info("--- Starting main function ---")
    driver = None
    try:
        driver = start_browser()
        login(driver)
        df = fetch_candidates(driver)
        save_and_upload(df)
    except Exception as e:
        logging.critical("--- A critical error occurred in main execution loop ---", exc_info=True)
    finally:
        if driver:
            logging.info("--- Closing browser session ---")
            driver.quit()
        logging.info("--- Script finished ---")

if __name__ == "__main__":
    main()
