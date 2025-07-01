import os
import sys
import time
import logging
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def upload_to_gcs(local_path, blob_name):
    try:
        client = storage.Client()
        bucket = client.bucket("recruitment-engine-cvs-sp-260625")
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)
        logging.info(f"✅ Uploaded to gs://recruitment-engine-cvs-sp-260625/{blob_name}")
    except Exception as e:
        logging.error(f"❌ Failed to upload to GCS: {e}")
        raise

def capture(driver, label):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
        driver.save_screenshot(path)
        upload_to_gcs(path, f"debug/{label}.png")
        os.remove(path)

def run():
    EMAIL = os.getenv("HIRE_USERNAME")
    PASSWORD = os.getenv("HIRE_PASSWORD")

    if not EMAIL or not PASSWORD:
        logging.error("❌ Missing env vars HIRE_USERNAME or HIRE_PASSWORD.")
        sys.exit(1)

    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = None
    try:
        service = Service(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 20)

        # Login
        logging.info("🌐 Opening login page")
        driver.get("https://clients.hireintelligence.io/login")

        wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log In')]"))).click()

        logging.info("🔐 Login submitted, waiting for dashboard...")
        wait.until(EC.url_contains("dashboard"))
        
        # Wait for dashboard to fully load — e.g., wait for "YOUR JOBS"
        wait.until(EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), 'YOUR JOBS')]")))
        logging.info("✅ Dashboard fully loaded!")
        capture(driver, "01_dashboard_loaded")

        time.sleep(2)  # Additional buffer to ensure stability

        # Navigate to multi-candidate admin
        logging.info("➡️ Navigating to multi-candidate admin...")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        time.sleep(5)
        capture(driver, "02_multi_candidate_admin")

        logging.info("📋 Navigation complete. You can now start scraping.")

        # [Optional: Add scraping logic here]

    except Exception as e:
        logging.error(f"❌ Script failed: {e}")
        if driver:
            capture(driver, "error")
        raise
    finally:
        if driver:
            driver.quit()
        logging.info("🧹 Browser closed")

if __name__ == "__main__":
    try:
        run()
        logging.info("✅ Script finished.")
    except Exception as e:
        logging.critical(f"Job failed: {e}")
        sys.exit(1)
