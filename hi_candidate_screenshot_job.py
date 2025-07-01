import os
import time
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from google.cloud import storage

# Define GCS bucket
BUCKET_NAME = os.getenv("DEBUG_SCREENSHOT_BUCKET", "recruitment-engine-cvs-sp-260625")
storage_client = storage.Client()

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox') # Crucial for containers
    chrome_options.add_argument('--disable-dev-shm-usage') # Prevents shared memory issues
    chrome_options.add_argument('--disable-gpu') # Important for headless environments
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    # Optional but good to have
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-setuid-sandbox') # Redundant with --no-sandbox, but belt-and-suspenders
    chrome_options.add_argument('--disable-features=NetworkService') # Sometimes helps with network errors

    # Add verbose logging for the Python-launched Chrome session
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log') # Changed name to differentiate

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    
    service = Service("/usr/bin/chromedriver") 

    return webdriver.Chrome(service=service, options=chrome_options)

def take_debug_screenshot(driver, name):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{name}_{timestamp}.png"
        print(f"[DEBUG] Saving screenshot: {filename}")
        success = driver.save_screenshot(filename)
        return filename if success else None
    except Exception as e:
        print(f"[ERROR] Failed to take screenshot: {e}")
        traceback.print_exc()
        return None

def upload_to_gcs(filename):
    if not os.path.exists(filename):
        print(f"[ERROR] File does not exist: {filename}")
        return
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"debug/{filename}")
        blob.upload_from_filename(filename)
        print(f"[DEBUG] Uploaded to GCS: gs://{BUCKET_NAME}/debug/{filename}")
    except Exception as e:
        print(f"[ERROR] GCS upload failed: {e}")
        traceback.print_exc()

def login_and_capture():
    print(f"[DEBUG] Starting screenshot job. GCS Bucket: {BUCKET_NAME}")
    driver = init_driver()
    wait = WebDriverWait(driver, 15)

    try:
        print("[DEBUG] Navigating to login page...")
        driver.get("https://clients.hireintelligence.io/login")
        filename = take_debug_screenshot(driver, "login_page_loaded")
        if filename:
            upload_to_gcs(filename)

        username = os.environ.get("HIRE_USERNAME")
        password = os.environ.get("HIRE_PASSWORD")
        print(f"[DEBUG] Using username: {username}")

        wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]"))).click()
        print("[DEBUG] Submitted login form.")

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Jobs Listed')]")))
        filename = take_debug_screenshot(driver, "dashboard_loaded")
        if filename:
            upload_to_gcs(filename)

        print("[DEBUG] Navigating to Multi-Candidate View...")
        multi_view_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(),'Multi-Candidate View')]")))
        multi_view_button.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Candidate Tracker')]")))
        filename = take_debug_screenshot(driver, "multi_candidate_view")
        if filename:
            upload_to_gcs(filename)

    except TimeoutException as e:
        print("[ERROR] Timeout waiting for page element:", e)
        filename = take_debug_screenshot(driver, "timeout_error")
        if filename:
            upload_to_gcs(filename)
    except Exception as e:
        print("[ERROR] Unexpected error:", e)
        traceback.print_exc()
        filename = take_debug_screenshot(driver, "unexpected_error")
        if filename:
            upload_to_gcs(filename)
    finally:
        print("[DEBUG] Closing browser.")
        driver.quit()

if __name__ == "__main__":
    login_and_capture()
