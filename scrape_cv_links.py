import os
import time
import logging
import tempfile
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage, secretmanager

# --- Logging setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv_scraper")

# --- Config ---
BUCKET_NAME = "recruitment-engine-cvs-sp-260625"
UPLOAD_PREFIX = "cvs/raw/"

# --- Secret Manager ---
def get_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ["GCP_PROJECT"]
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    return client.access_secret_version(request={"name": name}).payload.data.decode("UTF-8")

# --- GCS Upload ---
def upload_to_gcs(local_file, gcs_path):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_file)
    logger.info(f"Uploaded to GCS: gs://{BUCKET_NAME}/{gcs_path}")

# --- Selenium Setup ---
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# --- Main Scraper ---
def scrape_and_download_cvs():
    username = os.getenv("HIRE_USERNAME")
    password = get_secret("hire-password")
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

    try:
        logger.info("➡️ Opening login page...")
        driver.get("https://clients.hireintelligence.io/login")

        wait.until(EC.presence_of_element_located((By.ID, "Username"))).send_keys(username)
        driver.find_element(By.ID, "Password").send_keys(password)
        driver.find_element(By.ID, "submitButton").click()

        logger.info("🔐 Logging in...")

        wait.until(lambda d: "Jobs Listed" in d.page_source or "0 Jobs Listed" in d.page_source)
        logger.info("✅ Login successful")

        driver.get("https://clients.hireintelligence.io/multi-candidate-admin")
        logger.info("➡️ Navigated to multi-candidate-admin")

        wait.until(lambda d: "All [" in d.page_source)
        logger.info("✅ Page loaded with candidate list")

        # 🔍 Find CV download buttons (may need iframe handling if buried)
        links = driver.find_elements(By.XPATH, "//a[contains(@href, '/cv/download')]")
        logger.info(f"Found {len(links)} CV download links")

        for i, link in enumerate(links):
            url = link.get_attribute("href")
            logger.info(f"⬇️ Downloading CV {i + 1}: {url}")
            driver.execute_script("window.open(arguments[0]);", url)
            driver.switch_to.window(driver.window_handles[-1])

            # Wait briefly and save file from browser tab (workaround if direct GET fails)
            time.sleep(3)
            response = requests.get(url, cookies={c['name']: c['value'] for c in driver.get_cookies()})
            filename = f"cv_{i+1}.pdf"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(response.content)
                upload_to_gcs(tmp.name, f"{UPLOAD_PREFIX}{filename}")

            driver.close()
            driver.switch_to.window(driver.window_handles[0])

    except Exception as e:
        logger.error(f"❌ Error during scraping: {e}", exc_info=True)
    finally:
        driver.quit()
        logger.info("🧹 Driver closed")

if __name__ == "__main__":
    scrape_and_download_cvs()
