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
storage_client = storage.Client() # Global client for efficiency

# --- Function to test GCS connectivity (runs before Selenium init) ---
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

# --- Initializes the Selenium WebDriver ---
def init_driver():
    chrome_options = Options()
    # No --headless=new when using Xvfb (Xvfb provides the display)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage') # Prevents shared memory issues
    chrome_options.add_argument('--disable-gpu') # Good practice for headless environments
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222') # For potential remote debugging

    # Add Python-level Chrome logging for more info if it crashes later
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')
    
    # --- Critical for Xvfb: Point binary_location to the actual Chrome executable ---
    # The Xvfb display will be provided by the Docker ENTRYPOINT via DISPLAY=:99
    chrome_options.binary_location = "/opt/chrome/chrome" 

    print("[DEBUG] Initializing headless Chrome WebDriver with Xvfb/DISPLAY...")
    
    # Point to the ChromeDriver executable
    service = Service("/usr/bin/chromedriver") 

    return webdriver.Chrome(service=service, options=chrome_options)

# --- Takes a screenshot and returns the filename if successful ---
def take_debug_screenshot(driver, name):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{name}_{timestamp}.png"
        print(f"[DEBUG] Attempting to save screenshot to: {os.path.join(os.getcwd(), filename)}")
        success = driver.save_screenshot(filename)
        if success:
            print(f"Saved screenshot: {filename}")
            return filename
        else:
            print(f"[ERROR] driver.save_screenshot() returned False for {filename}")
            return None
    except Exception as e:
        print(f"[ERROR] Failed to take screenshot: {e}")
        traceback.print_exc()
        return None

# --- Uploads a local file to GCS ---
def upload_to_gcs(filename):
    if not os.path.exists(filename):
        print(f"[ERROR] File does not exist locally: {filename}. Cannot upload to GCS.")
        return
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"debug/{filename}")
        print(f"[DEBUG] Attempting GCS upload for {filename} to gs://{BUCKET_NAME}/debug/{filename}")
        blob.upload_from_filename(filename)
        print(f"Uploaded {filename} to gs://{BUCKET_NAME}/debug/{filename}")
    except Exception as e:
        print(f"[ERROR] GCS upload failed for {filename}: {e}")
        traceback.print_exc()
    finally:
        # Clean up local file after upload attempt
        try:
            if os.path.exists(filename):
                os.remove(filename)
                print(f"Deleted local screenshot file: {filename}")
        except Exception as e:
            print(f"Failed to delete local file {filename}: {e}")


# --- Main logic for login and capture ---
def login_and_capture():
    print(f"[DEBUG] Starting screenshot job. GCS Bucket: {BUCKET_NAME}")
    
    # --- CRITICAL: Call GCS connectivity test first ---
    if not test_gcs_upload():
        print("[ERROR] GCS connectivity test failed. Aborting script as GCS is required.")
        return # Abort if GCS upload test fails

    print("[DEBUG] Attempting to initialize WebDriver...")
    driver = None # Initialize driver to None for finally block
    try:
        driver = init_driver()
        print("[DEBUG] WebDriver initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize WebDriver: {e}")
        traceback.print_exc()
        # Attempt to capture Chrome's own debug log if initialization fails
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
        print(f"[DEBUG] Using username: {username}") # Consider masking username in production

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
        filename = take_debug_screenshot(driver, "timeout_error") # Take error screenshot
        if filename:
            upload_to_gcs(filename)
    except Exception as e:
        print("[ERROR] Unexpected error:", e)
        traceback.print_exc()
        filename = take_debug_screenshot(driver, "unexpected_error") # Take error screenshot
        if filename:
            upload_to_gcs(filename)
    finally:
        if driver: # Ensure driver exists before quitting
            print("[DEBUG] Closing browser.")
            driver.quit()
        else:
            print("[DEBUG] Driver not initialized, no browser to close.")


if __name__ == "__main__":
    login_and_capture()
