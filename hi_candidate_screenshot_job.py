import os
import time
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from google.cloud import storage

# Set default bucket if not set via env
BUCKET_NAME = os.environ.get("DEBUG_SCREENSHOT_BUCKET", "recruitment-engine-cvs-sp-260625")
storage_client = storage.Client()

def init_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--enable-logging')
    options.add_argument('--v=1')
    options.add_argument('--log-path=/tmp/chrome_debug.log')

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def take_debug_screenshot(driver, name):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{name}_{timestamp}.png"
        print(f"[DEBUG] Attempting to save screenshot to: {filename}")
        success = driver.save_screenshot(filename)
        if not success:
            print(f"[ERROR] driver.save_screenshot returned False for {filename}")
        return filename if success else None
    except Exception as e:
        print(f"[ERROR] Failed to save screenshot: {e}")
        return None

def upload_to_gcs(filename):
    if not os.path.exists(filename):
        print(f"[ERROR] File not found for upload: {filename}")
        return
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"debug/{filename}")
        blob.upload_from_filename(filename)
        print(f"[DEBUG] Uploaded screenshot to GCS: gs://{BUCKET_NAME}/debug/{filename}")
    except Exception as e:
        print(f"[ERROR] Failed to upload to GCS: {e}")

def login_and_capture():
    print("[DEBUG] Starting login and screenshot capture flow...")
    print(f"[DEBUG] Using GCS bucket: {BUCKET_NAME}")
    driver = init_driver()
    wait = WebDriverWait(driver, 15)

    try:
        print("[DEBUG] Navigating to login page...")
        driver.get("https://hireintelligence.io")
        filename = take_debug_screenshot(driver, "login_page_loaded")
        if filename:
            upload_to_gcs(filename)

        username = os.environ.get("HIRE_USERNAME")
        password = os.environ.get("HIRE_PASSWORD")
        print(f"[DEBUG] Using username: {username}")

        try:
            wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(username)
        except TimeoutException:
            print("[ERROR] Login field not found – likely Chrome failed to start or page didn't load.")
            filename = take_debug_screenshot(driver, "login_timeout")
            if filename:
                upload_to_gcs(filename)
            raise

        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]"))).click()
        print("[DEBUG] Login submitted.")

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Jobs Listed')]")))
        print("[DEBUG] Dashboard loaded.")
        filename = take_debug_screenshot(driver, "dashboard_loaded")
        if filename:
            upload_to_gcs(filename)

        print("[DEBUG] Navigating to Multi-Candidate View...")
        multi_candidate_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(),'Multi-Candidate View')]")))
        multi_candidate_button.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Candidate Tracker')]")))
        print("[DEBUG] Multi-candidate view loaded.")
        filename = take_debug_screenshot(driver, "multi_candidate_view")
        if filename:
            upload_to_gcs(filename)

    except TimeoutException as e:
        print("[ERROR] Timeout while waiting for page elements:", e)
        traceback.print_exc()
    except Exception as e:
        print("[ERROR] An unexpected error occurred:", e)
        traceback.print_exc()
    finally:
        print("[DEBUG] Closing browser.")
        driver.quit()

if __name__ == "__main__":
    login_and_capture()
