import os
import time
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage
import logging

# --- DETAILED LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load credentials from environment
USERNAME = os.getenv("HIRE_USERNAME")
PASSWORD = os.getenv("HIRE_PASSWORD")
LOGIN_URL = "https://clients.hireintelligence.io/"
CANDIDATE_URL = "https://clients.hireintelligence.io/candidates"
BUCKET_NAME = os.getenv("CV_BUCKET_NAME", "intelligent-recruitment-cvs")

def start_browser():
    logging.info("--- Entering start_browser function ---")
    try:
        logging.info("Initializing ChromeOptions...")
        options = uc.ChromeOptions()
        
        # Using minimal options to start
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument('--window-size=1280,720')

        logging.info(f"Browser executable path: /opt/chrome/chrome")
        logging.info(f"Driver executable path: /usr/local/bin/chromedriver")

        logging.info("Calling uc.Chrome()...")
        driver = uc.Chrome(
            browser_executable_path="/opt/chrome/chrome",
            driver_executable_path="/usr/local/bin/chromedriver",
            options=options,
            version_main=127,
            enable_cdp_events=True # Added for more verbose logging if needed
        )
        logging.info("--- uc.Chrome() call SUCCEEDED ---")
        return driver
    except Exception as e:
        logging.critical(f"--- CRITICAL ERROR IN start_browser ---")
        logging.critical(f"Error type: {type(e).__name__}")
        logging.critical(f"Error message: {e}", exc_info=True)
        raise

def login(driver):
    # This function remains the same for now
    print("🔐 Navigating to login page...")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)
    try:
        form_container = wait.until(EC.presence_of_element_located((By.ID, "email")))
        print("⏳ Pausing to allow bot detection scripts to run...")
        time.sleep(3)
        email_input = driver.find_element(By.ID, "email")
        password_input = driver.find_element(By.ID, "password")
        login_button = driver.find_element(By.XPATH, '//button[contains(text(), "Login")]')
        print("📝 Simulating user actions and submitting login form...")
        actions = ActionChains(driver)
        actions.move_to_element(email_input).pause(0.5).click().send_keys(USERNAME).pause(0.5)
        actions.move_to_element(password_input).pause(0.5).click().send_keys(PASSWORD).pause(0.5)
        actions.move_to_element(login_button).click()
        actions.perform()
    except Exception as e:
        print(f"❌ An error occurred during the login process: {e}")
        driver.save_screenshot("login_error_screenshot.png")
        raise
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Jobs Listed")]')))
    print("✅ Logged in successfully.")


def fetch_candidates(driver):
    # This function remains the same
    print("📥 Navigating to candidates page...")
    driver.get(CANDIDATE_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
    print(f"📄 Found {len(rows)} candidate rows.")
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
    # This function remains the same
    if df.empty:
        print("⚠️ No candidate data found to save.")
        return
    filename = f"hi_candidates_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    df.to_excel(filename, index=False)
    print(f"💾 Report saved locally as {filename}")
    print("☁️ Uploading report to Google Cloud Storage...")
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"reports/{filename}")
    blob.upload_from_filename(filename)
    print(f"✅ Uploaded to: gs://{BUCKET_NAME}/reports/{filename}")


def main():
    logging.info("--- Starting main function ---")
    driver = None
    try:
        driver = start_browser()
        login(driver)
        df = fetch_candidates(driver)
        save_and_upload(df)
    except Exception as e:
        logging.error("--- An error occurred in main execution loop ---")
        logging.error(f"Error type: {type(e).__name__}")
        logging.error(f"Error message: {e}", exc_info=True)
    finally:
        if driver:
            logging.info("--- Closing browser session ---")
            driver.quit()
        logging.info("--- Script finished ---")

if __name__ == "__main__":
    main()
