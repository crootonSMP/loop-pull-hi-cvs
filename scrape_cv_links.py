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

def run():
    EMAIL = os.getenv("HIRE_USERNAME")
    PASSWORD = os.getenv("HIRE_PASSWORD")

    if not EMAIL or not PASSWORD:
        logging.error("❌ Missing environment variables HIRE_USERNAME or HIRE_PASSWORD.")
        sys.exit(1)

    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = None
    try:
        # Start Chrome
        service = Service(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 20)

        # Go to login page
        logging.info("🌐 Navigating to login page")
        driver.get("https://clients.hireintelligence.io/login")

        # Fill and submit login form
        wait.until(EC.presence_of_element_located((By.ID, "email")))
        driver.find_element(By.ID, "email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log In')]")))
        login_button.click()

        # Wait for login to complete
        logging.info("🔐 Submitted login, waiting for dashboard...")
        try:
            wait.until(EC.url_contains("dashboard"))
            logging.info("🎉 Login successful!")
            time.sleep(5)  # Let iframes load

            # Optional: check for iframes
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            logging.info(f"🧾 Found {len(iframes)} iframe(s) on the dashboard.")

            # Screenshot for confirmation
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                path = tmp.name
                driver.save_screenshot(path)
                upload_to_gcs(path, "debug/dashboard_loaded.png")
                os.remove(path)

        except TimeoutException:
            logging.error("❌ Login failed or dashboard did not load in time.")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                path = tmp.name
                driver.save_screenshot(path)
                upload_to_gcs(path, "debug/login_failed_dashboard_timeout.png")
                os.remove(path)
            raise

        # Navigate to candidate admin page (required for scraping)
        logging.info("➡️ Navigating to multi-candidate admin page")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        time.sleep(5)  # Let full content/iframes load

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = tmp.name
            driver.save_screenshot(path)
            upload_to_gcs(path, "debug/multi_candidate_admin.png")
            os.remove(path)

        # [NEXT STEP: Add scraping logic here to extract file names or download links.]

    except Exception as e:
        logging.error(f"❌ Script failed: {e}")
        if driver:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                path = tmp.name
                driver.save_screenshot(path)
                upload_to_gcs(path, "debug/error.png")
                os.remove(path)
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
