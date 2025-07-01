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
        logging.info(f"📤 Uploaded screenshot to gs://recruitment-engine-cvs-sp-260625/{blob_name}")
    except Exception as e:
        logging.error(f"❌ Failed to upload screenshot to GCS: {e}")

def capture(driver, name):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        driver.save_screenshot(tmp.name)
        upload_to_gcs(tmp.name, f"debug/{name}.png")
        os.remove(tmp.name)

def run():
    EMAIL = os.getenv("HIRE_USERNAME")
    PASSWORD = os.getenv("HIRE_PASSWORD")

    if not EMAIL or not PASSWORD:
        logging.error("Missing login credentials.")
        sys.exit(1)

    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(executable_path="/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # Step 1: Log in
        driver.get("https://clients.hireintelligence.io/login")
        wait.until(EC.presence_of_element_located((By.ID, "email")))

        driver.find_element(By.ID, "email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()

        # Step 2: Wait for dashboard
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'YOUR JOBS')]")))
        logging.info("✅ Logged in successfully")

        capture(driver, "01_dashboard_loaded")

        # Step 3: Manually go to multi-candidate-admin
        logging.info("➡ Navigating to multi-candidate-admin")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")

        # Step 4: Wait for a known element
        wait.until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'MULTI-CANDIDATE ADMIN')]")))
        logging.info("✅ Reached Multi-Candidate Admin page")

        capture(driver, "02_multi_candidate_admin_loaded")

    except Exception as e:
        logging.error(f"💥 Error: {e}")
        capture(driver, "error")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    run()
