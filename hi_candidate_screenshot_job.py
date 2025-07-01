import os
import sys

print("[DEBUG] Script starting: Initial print executed.") # This *must* appear

try:
    print("[DEBUG] Attempting import time...")
    import time
    print("[DEBUG] import time successful.")

    print("[DEBUG] Attempting import traceback...")
    import traceback
    print("[DEBUG] import traceback successful.")

    print("[DEBUG] Attempting import datetime...")
    from datetime import datetime
    print("[DEBUG] import datetime successful.")

    print("[DEBUG] Attempting import google.cloud.storage...")
    from google.cloud import storage
    print("[DEBUG] import google.cloud.storage successful.")

    # --- Add the GCS test function (copy it from your full script) ---
    # Define GCS bucket
    BUCKET_NAME = os.getenv("DEBUG_SCREENSHOT_BUCKET", "recruitment-engine-cvs-sp-260625")
    storage_client = storage.Client()

    def test_gcs_upload():
        test_filename = f"gcs_test_import_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        test_content = f"Import debug test from Cloud Run at {datetime.now().isoformat()}."
        test_blob_name = f"debug_import/{test_filename}" 

        print(f"[DEBUG] Attempting to upload GCS import test file: {test_blob_name}")
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(test_blob_name)
            blob.upload_from_string(test_content)
            print(f"[DEBUG] Successfully uploaded GCS import test file: gs://{BUCKET_NAME}/{test_blob_name}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to upload GCS import test file: {e}")
            traceback.print_exc()
            return False
    # --- End GCS test function ---

    if not test_gcs_upload():
        print("[ERROR] GCS connectivity test failed. Aborting script.")
        sys.exit(1) # Exit with error if GCS fails here

    print("[DEBUG] Attempting import selenium...")
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    print("[DEBUG] import selenium successful.")

    print("[DEBUG] All imports successful. Script should now try init_driver().")

    # --- Keep only init_driver call and wrap in try/except ---
    # No need for full login_and_capture yet.
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--verbose')
        chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')
        
        print("[DEBUG] Initializing headless Chrome WebDriver...")
        service = Service(log_path="/tmp/chromedriver_debug.log", verbose=True) 
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("[DEBUG] WebDriver initialized successfully.")
        driver.quit() # Quit immediately after successful init for this test
        print("[DEBUG] WebDriver quit successfully for test.")

    except Exception as e:
        print(f"[ERROR] WebDriver initialization or basic usage failed: {e}")
        traceback.print_exc()
        if os.path.exists("/tmp/chrome_debug_python.log"):
            print("--- Contents of /tmp/chrome_debug_python.log after init failure ---")
            with open("/tmp/chrome_debug_python.log", "r") as f:
                print(f.read())
            print("--- End contents of /tmp/chrome_debug_python.log ---")
        else:
            print("No /tmp/chrome_debug_python.log found.")

        if os.path.exists("/tmp/chromedriver_debug.log"):
            print("--- Contents of /tmp/chromedriver_debug.log after init failure ---")
            with open("/tmp/chromedriver_debug.log", "r") as f:
                print(f.read())
            print("--- End contents of /tmp/chromedriver_debug.log ---")
        else:
            print("No /tmp/chromedriver_debug.log found.")

finally:
    if driver:
        driver.quit() # Ensure driver is quit even if other errors occur
    print("[DEBUG] Script ending: Finally block executed.")
