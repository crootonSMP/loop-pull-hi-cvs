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
import sys

print("[DEBUG] Script started: __main__ block executing.")
sys.stdout.flush()
sys.stderr.flush()

BUCKET_NAME = os.getenv("DEBUG_SCREENSHOT_BUCKET", "recruitment-engine-cvs-sp-260625")
storage_client = storage.Client()

def test_gcs_upload():
    print("[DEBUG] Entered test_gcs_upload()")
    sys.stdout.flush()
    sys.stderr.flush()

    test_filename = f"gcs_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    test_content = f"This is a test file uploaded from Cloud Run at {datetime.now().isoformat()}."
    test_blob_name = f"debug_test/{test_filename}"

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(test_blob_name)
        blob.upload_from_string(test_content)
        print(f"[DEBUG] Successfully uploaded GCS test file: gs://{BUCKET_NAME}/{test_blob_name}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to upload GCS test file: {e}")
        traceback.print_exc()
        return False

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')
    chrome_options.add_argument('--no-zygote')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--no-proxy-server')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-client-side-phishing-detection')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--disable-hang-monitor')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-prompt-on-repost')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--disable-translate')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--enable-automation')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--allow-insecure-localhost')

    temp_user_data_dir = os.path.join("/tmp", "chrome-user-data-" + str(int(time.time())))
    chrome_options.add_argument(f'--user-data-dir={temp_user_data_dir}')

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    service = Service(log_path="/tmp/chromedriver_debug.log", verbose=True)
    return webdriver.Chrome(service=service, options=chrome_options)

def take_debug_screenshot(driver, name):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{name}_{timestamp}.png"
        print(f"[DEBUG] Attempting to save screenshot: {filename}")
        success = driver.save_screenshot(filename)
        if success:
            print(f"[INFO] Screenshot saved: {filename}")
            return filename
        else:
            print(f"[ERROR] driver.save_screenshot() returned False for {filename}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception in take_debug_screenshot: {e}")
        traceback.print_exc()
        return None

def upload_to_gcs(filename):
    if not filename:
        print("[ERROR] No filename passed to upload_to_gcs() — skipping upload.")
        return
    if not os.path.exists(filename):
        print(f"[ERROR] File not found: {filename}")
        return
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"debug/{filename}")
        print(f"[DEBUG] Uploading {filename} to GCS...")
        blob.upload_from_filename(filename)
        print(f"[INFO] Uploaded to gs://{BUCKET_NAME}/debug/{filename}")
    except Exception as e:
        print(f"[ERROR] GCS upload failed: {e}")
        traceback.print_exc()
    finally:
        try:
            os.remove(filename)
            print(f"[INFO] Deleted local screenshot: {filename}")
        except Exception as e:
            print(f"[WARN] Could not delete local file: {e}")

def login_and_capture():
    print(f"[DEBUG] Starting screenshot job. GCS Bucket: {BUCKET_NAME}")

    if not test_gcs_upload():
        print("[ERROR] GCS test failed. Exiting.")
        sys.exit(1)

    username = os.environ.get("HIRE_USERNAME")
    password = os.environ.get("HIRE_PASSWORD")
    if not username or not password:
        print("[ERROR] Missing HIRE_USERNAME or HIRE_PASSWORD env vars.")
        sys.exit(1)

    driver = None
    try:
        driver = init_driver()
        wait = WebDriverWait(driver, 15)

        print("[DEBUG] Navigating to login page...")
        driver.get("https://clients.hireintelligence.io/login")
        upload_to_gcs(take_debug_screenshot(driver, "login_page_loaded"))

        wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]"))).click()

        print("[DEBUG] Login submitted.")
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Jobs Listed')]")))
        upload_to_gcs(take_debug_screenshot(driver, "dashboard_loaded"))

        print("[DEBUG] Navigating to Multi-Candidate View...")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Multi-Candidate View')]"))).click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Candidate Tracker')]")))
        upload_to_gcs(take_debug_screenshot(driver, "multi_candidate_view"))

        # Optional final state screenshot
        upload_to_gcs(take_debug_screenshot(driver, "final_state"))

        print("[SUCCESS] Script completed successfully.")
    except TimeoutException as e:
        print("[ERROR] TimeoutException:", e)
        traceback.print_exc()
        upload_to_gcs(take_debug_screenshot(driver, "timeout_error"))
    except Exception as e:
        print("[ERROR] Unexpected error:", e)
        traceback.print_exc()
        upload_to_gcs(take_debug_screenshot(driver, "unexpected_error"))
    finally:
        if driver:
            print("[DEBUG] Closing browser.")
            driver.quit()
        else:
            print("[WARN] WebDriver not initialized — skipping quit.")

if __name__ == "__main__":
    login_and_capture()
