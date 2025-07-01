import os
import sys
import logging
import tempfile
import time
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
        logging.info(f"✅ Uploaded to gs://recruitment-engine-cvs-sp-260625/{blob_name}")
    except Exception as e:
        logging.error(f"❌ Failed to upload to GCS: {e}")
        raise

def run():
    EMAIL = os.getenv("HIRE_USERNAME")
    PASSWORD = os.getenv("HIRE_PASSWORD")

    if not EMAIL or not PASSWORD:
        logging.error("❌ Missing environment variables.")
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

        logging.info("🌐 Navigating to login page")
        driver.get("https://clients.hireintelligence.io/login")

        wait = WebDriverWait(driver, 20)

        wait.until(EC.presence_of_element_located((By.ID, "email")))
        driver.find_element(By.ID, "email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)

        driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()

        logging.info("🔐 Submitted login, waiting for dashboard...")
        wait.until(EC.url_contains("dashboard"))
        logging.info("🎉 Login successful!")

        time.sleep(5)

        # Go to multi-candidate-admin
        logging.info("🌐 Navigating to multi-candidate-admin page")
        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")

        time.sleep(5)

        # OPTIONAL: Print iframe sources
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        logging.info(f"🧾 Found {len(iframes)} iframes")
        for i, frame in enumerate(iframes):
            try:
                src = frame.get_attribute("src")
                logging.info(f"📎 iframe[{i}] src: {src}")
            except Exception:
                continue

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = tmp.name
            driver.save_screenshot(path)
            upload_to_gcs(path, "debug/multi_candidate_iframes.png")
            os.remove(path)

    except Exception as e:
        logging.error(f"❌ Error occurred: {e}")
        if driver:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                fail_path = tmp.name
                driver.save_screenshot(fail_path)
                upload_to_gcs(fail_path, "debug/failure.png")
                os.remove(fail_path)
        raise
    finally:
        if driver:
            driver.quit()
        logging.info("🧹 Closed browser")

if __name__ == "__main__":
    try:
        run()
        logging.info("✅ Done.")
    except Exception as e:
        logging.critical(f"Job failed: {e}")
        sys.exit(1)
