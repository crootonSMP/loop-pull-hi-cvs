import os
import sys
import time
import tempfile
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def upload_to_gcs(local_path, blob_name):
    try:
        client = storage.Client()
        bucket = client.bucket("recruitment-engine-cvs-sp-260625")
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)
        logging.info(f"✅ Uploaded screenshot to GCS: gs://recruitment-engine-cvs-sp-260625/{blob_name}")
    except Exception as e:
        logging.error(f"❌ Failed to upload screenshot to GCS: {e}")

def capture(driver, name):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
        driver.save_screenshot(path)
        upload_to_gcs(path, f"debug/{name}.png")
        os.remove(path)

def run():
    EMAIL = os.getenv("HIRE_USERNAME")
    PASSWORD = os.getenv("HIRE_PASSWORD")

    if not EMAIL or not PASSWORD:
        logging.error("❌ Missing login credentials in environment variables.")
        sys.exit(1)

    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    service = Service(executable_path="/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 20)

    try:
        logging.info("🌐 Navigating to login page")
        driver.get("https://clients.hireintelligence.io/login")
        wait.until(EC.presence_of_element_located((By.ID, "email")))

        email_input = driver.find_element(By.ID, "email")
        password_input = driver.find_element(By.ID, "password")
        email_input.clear()
        email_input.send_keys(EMAIL)
        password_input.clear()
        password_input.send_keys(PASSWORD)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log In')]")))
        login_button.click()

        logging.info("🔐 Submitted login, waiting for dashboard...")
        wait.until(EC.url_contains("dashboard"))

        capture(driver, "01_logged_in_dashboard")

        # Wait for dashboard to fully load
        time.sleep(6)

        # NOW go directly to the multi-candidate-admin page
        logging.info("➡️ Navigating to multi-candidate admin page...")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")

        # Wait for something unique on the page to confirm it's loaded
        wait.until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'MULTI-CANDIDATE ADMIN')]")))
        logging.info("✅ Reached Multi-Candidate Admin page")

        capture(driver, "02_multi_candidate_admin")

    except Exception as e:
        logging.error(f"❌ Error during process: {e}")
        capture(driver, "error")
        raise
    finally:
        driver.quit()
        logging.info("🧹 Browser closed")

if __name__ == "__main__":
    try:
        run()
        logging.info("✅ Finished navigation successfully")
    except Exception as e:
        logging.critical(f"💥 Script failed: {e}")
        sys.exit(1)

