import os
import requests
import pandas as pd
from datetime import datetime
from google.cloud import storage
import logging
import time

# ✅ IMPORT VANILLA SELENIUM
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables ---
USERNAME = os.getenv("HIRE_USERNAME")
PASSWORD = os.getenv("HIRE_PASSWORD")
API_KEY = os.getenv("HIRE_API_KEY") # We will now use the API key
LOGIN_API_URL = "https://clients.hireintelligence.io/api/v1/auth/login"
CANDIDATE_URL = "https://clients.hireintelligence.io/candidates"
BUCKET_NAME = os.getenv("CV_BUCKET_NAME", "intelligent-recruitment-cvs")

def api_login():
    """Performs login via API to get a session cookie, avoiding the bot-protected web form."""
    logging.info("🔐 Attempting login via API...")
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "email": USERNAME,
        "password": PASSWORD
    }
    
    session = requests.Session()
    response = session.post(LOGIN_API_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        logging.info("✅ API Login successful.")
        # Return the session object which contains the necessary cookies
        return session.cookies
    else:
        logging.error(f"❌ API Login failed with status code {response.status_code}: {response.text}")
        raise Exception("API Login failed.")

def start_browser_with_session(session_cookies):
    """Starts a browser and injects the session cookies."""
    logging.info("🚀 Launching Chrome browser to inject session...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,720")
    
    driver_path = "/usr/local/bin/chromedriver"
    service = Service(executable_path=driver_path)

    driver = webdriver.Chrome(service=service, options=options)
    
    # The key part: Inject the cookies into the browser
    # Must navigate to the domain first before you can add cookies for it
    driver.get(CANDIDATE_URL) 
    time.sleep(1) # Small pause to ensure the page is ready for cookies
    
    for cookie in session_cookies:
        driver.add_cookie({
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain,
            'path': cookie.path,
            'secure': cookie.secure,
            'httpOnly': cookie.secure, # Assume httpOnly if secure
        })
    logging.info("🍪 Session cookies injected successfully.")
    
    return driver

def fetch_candidates(driver):
    """Fetches candidate data from the now-logged-in browser session."""
    logging.info("📥 Navigating to candidates page...")
    # Navigate to the page again to load it with the new session
    driver.get(CANDIDATE_URL) 
    
    # Wait for the table to be present
    wait = webdriver.support.ui.WebDriverWait(driver, 20)
    wait.until(webdriver.support.expected_conditions.presence_of_element_located((webdriver.common.by.By.TAG_NAME, "table")))
    
    rows = driver.find_elements(webdriver.common.by.By.XPATH, "//table//tbody//tr")
    logging.info(f"📄 Found {len(rows)} candidate rows.")
    data = []
    for row in rows:
        cols = row.find_elements(webdriver.common.by.By.TAG_NAME, "td")
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
        # New authentication flow
        session_cookies = api_login()
        driver = start_browser_with_session(session_cookies)
        
        # Now fetch the data
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
