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
import sys # <--- ADD THIS IMPORT

print("[DEBUG] Script started: __main__ block executing.")
sys.stdout.flush() # <--- ADD THIS
sys.stderr.flush() # <--- ADD THIS

# Define GCS bucket
BUCKET_NAME = os.getenv("DEBUG_SCREENSHOT_BUCKET", "recruitment-engine-cvs-sp-260625")
storage_client = storage.Client()

# --- Function to test GCS connectivity ---
def test_gcs_upload():
    print("[DEBUG] Entered test_gcs_upload()")
    sys.stdout.flush() # <--- ADD THIS
    sys.stderr.flush() # <--- ADD THIS
    # ... (rest of test_gcs_upload) ...

# --- Initializes the Selenium WebDriver ---
def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    sys.stdout.flush() # <--- ADD THIS
    sys.stderr.flush() # <--- ADD THIS
    
    service = Service(log_path="/tmp/chromedriver_debug.log", verbose=True) 

    return webdriver.Chrome(service=service, options=chrome_options)

# ... (rest of your functions) ...

# --- Main workflow ---
def login_and_capture():
    print(f"[DEBUG] Starting screenshot job. GCS Bucket: {BUCKET_NAME}")
    sys.stdout.flush() # <--- ADD THIS
    sys.stderr.flush() # <--- ADD THIS

    if not test_gcs_upload():
        print("[ERROR] GCS connectivity test failed. Aborting script as GCS is required.")
        sys.stdout.flush() # <--- ADD THIS
        sys.stderr.flush() # <--- ADD THIS
        return

    print("[DEBUG] Attempting to initialize WebDriver...")
    sys.stdout.flush() # <--- ADD THIS
    sys.stderr.flush() # <--- ADD THIS
    driver = None 
    try:
        driver = init_driver()
        print("[DEBUG] WebDriver initialized successfully.")
        sys.stdout.flush() # <--- ADD THIS
        sys.stderr.flush() # <--- ADD THIS
    except Exception as e:
        print(f"[ERROR] Failed to initialize WebDriver: {e}")
        sys.stdout.flush() # <--- ADD THIS
        sys.stderr.flush() # <--- ADD THIS
        traceback.print_exc()
        sys.stdout.flush() # <--- ADD THIS
        sys.stderr.flush() # <--- ADD THIS
        # ... (rest of the error logging for /tmp/chrome_debug_python.log etc.) ...
        return

    # ... (rest of the try block, add flushes after critical print statements) ...

    finally:
        if driver:
            print("[DEBUG] Closing browser.")
            sys.stdout.flush() # <--- ADD THIS
            sys.stderr.flush() # <--- ADD THIS
            driver.quit()
        else:
            print("[DEBUG] Driver not initialized, no browser to close.")
            sys.stdout.flush() # <--- ADD THIS
            sys.stderr.flush() # <--- ADD THIS


if __name__ == "__main__":
    login_and_capture()
