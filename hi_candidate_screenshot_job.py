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
storage_client = storage.Client() # Global client is good

# --- NEW FUNCTION FOR GCS TEST ---
def test_gcs_upload():
    test_filename = f"gcs_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    test_content = f"This is a test file uploaded from Cloud Run at {datetime.now().isoformat()}."
    test_blob_name = f"debug_test/{test_filename}" # Use a slightly different path for test files

    print(f"[DEBUG] Attempting to upload GCS test file: {test_blob_name}")
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
# --- END NEW FUNCTION ---

# --- init_driver function (correctly positioned) ---
def init_driver():
    chrome_options = Options()
    # No --headless=new when using Xvfb with binary_location pointing to Chrome
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu') # Still good practice for headless
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    # Add Python-level Chrome logging for more info if it crashes later
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')
    
    # --- Critical for Xvfb: Point binary_location to the actual Chrome executable ---
    # The Xvfb display will be provided by the Docker ENTRYPOINT
    chrome_options.binary_location = "/opt/chrome/chrome" 

    print("[DEBUG] Initializing headless Chrome WebDriver with Xvfb/DISPLAY...")
    
    service = Service("/usr/bin/chromedriver") # Point to the ChromeDriver executable

    return webdriver.Chrome(service=service, options=chrome_options)
# --- END init_driver function ---

# --- take_debug_screenshot function ---
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
# --- END take_debug_screenshot function ---

# --- upload_to_gcs function ---
def upload_to_gcs(filename):
    if not os.path.exists(filename):
        print(f"[ERROR] File does not exist locally: {filename}")
        return
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"debug/{filename}")
        blob.upload_from_filename(filename)
        print(f"[DEBUG] Uploaded to GCS: gs://{BUCKET_NAME}/debug/{filename}")
    except Exception as e:
        print(f"[ERROR] GCS upload failed: {e}")
        traceback.print_exc()
# --- END upload_to_gcs function ---

# --- login_and_capture function (complete and correctly positioned) ---
def login_and_capture():
    print(f"[DEBUG] Starting screenshot job. GCS Bucket: {BUCKET_NAME}")
    
    # --- CALL NEW GCS TEST FUNCTION HERE (runs before driver init) ---
    if not test_gcs_upload():
        print("[ERROR] GCS connectivity test failed. This is a critical issue. Aborting script.")
        return # Abort if GCS upload test fails

    print("[DEBUG] Attempting to initialize WebDriver...")
    try:
        driver = init_driver()
        print("[DEBUG] WebDriver initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize WebDriver: {e}")
        traceback.print_exc()
        # Try to capture Chrome's own debug log if initialization fails
        if os.path.exists("/tmp/chrome_debug_python.log"):
            print("--- Contents of /tmp/chrome_debug_python.log after init failure ---")
            with open("/tmp/chrome_debug_python.log", "r") as f:
                print(f.read())
            print("--- End contents of /tmp/chrome_debug_python.log ---")
        else:
            print("No /tmp/chrome_debug_python.log found after init failure.")
        return # Abort if driver fails to init

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
        print("[DEBUG] Dashboard loaded.")
        filename = take_debug_screenshot(driver, "dashboard_loaded")
        if filename:
            upload_to_gcs(filename)

        print("[DEBUG] Navigating to Multi-Candidate View...")
        multi_view_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(),'Multi-Candidate View')]")))
        multi_view_button.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Candidate Tracker')]")))
        print("[DEBUG] Multi-candidate view loaded.")
        filename = take_debug_screenshot(driver, "multi_candidate_view")
        if filename:
            upload_to_gcs(filename)

    except TimeoutException as e:
        print("[ERROR] Timeout waiting for page element:", e)
        traceback.print_exc()
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
# --- END login_and_capture function ---

if __name__ == "__main__":
    login_and_capture()
