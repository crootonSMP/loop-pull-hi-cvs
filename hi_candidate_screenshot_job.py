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
import sys # Added for explicit flush

print("[DEBUG] Script started: __main__ block executing.") # TOP-LEVEL ENTRY POINT
sys.stdout.flush() # Ensure this initial print is seen
sys.stderr.flush() # Ensure this initial print is seen

# Define GCS bucket
BUCKET_NAME = os.getenv("DEBUG_SCREENSHOT_BUCKET", "recruitment-engine-cvs-sp-260625")
storage_client = storage.Client() # Global client for efficiency

# --- Function to test GCS connectivity ---
def test_gcs_upload():
    print("[DEBUG] Entered test_gcs_upload()")
    sys.stdout.flush() # Ensure this print is seen
    sys.stderr.flush() # Ensure this print is seen

    test_filename = f"gcs_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    test_content = f"This is a test file uploaded from Cloud Run at {datetime.now().isoformat()}."
    test_blob_name = f"debug_test/{test_filename}"

    print(f"[DEBUG] Attempting to upload GCS test file: {test_blob_name}")
    sys.stdout.flush() # Ensure this print is seen
    sys.stderr.flush() # Ensure this print is seen

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(test_blob_name)
        blob.upload_from_string(test_content)
        print(f"[DEBUG] Successfully uploaded GCS test file: gs://{BUCKET_NAME}/{test_blob_name}")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
        return True
    except Exception as e:
        print(f"[ERROR] Failed to upload GCS test file: {e}")
        sys.stdout.flush() # Ensure error print is seen
        traceback.print_exc() # Print the full traceback
        sys.stderr.flush() # CRITICAL: Ensure traceback is flushed to stderr
        return False

# --- Initializes the Selenium WebDriver ---
def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu') # Good practice for headless
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    # chrome_options.add_argument('--verbose') # This line remains commented out/removed
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log') # Chrome's own logs (stdout/stderr)

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    sys.stdout.flush() # Ensure this print is seen
    sys.stderr.flush() # Ensure this print is seen
    
    # --- CRITICAL: Use Service with verbose ChromeDriver logging ---
    service = Service(log_path="/tmp/chromedriver_debug.log", verbose=True) 

    return webdriver.Chrome(service=service, options=chrome_options)

# --- Takes a screenshot and returns the filename if successful ---
def take_debug_screenshot(driver, name):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{name}_{timestamp}.png"
        print(f"[DEBUG] Attempting to save screenshot to: {os.path.join(os.getcwd(), filename)}")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
        success = driver.save_screenshot(filename)
        if success:
            print(f"Saved screenshot: {filename}")
            sys.stdout.flush() # Ensure this print is seen
            sys.stderr.flush() # Ensure this print is seen
            return filename
        else:
            print(f"[ERROR] driver.save_screenshot() returned False for {filename}")
            sys.stdout.flush() # Ensure this print is seen
            sys.stderr.flush() # Ensure this print is seen
            return None
    except Exception as e:
        print(f"[ERROR] Failed to take screenshot: {e}")
        sys.stdout.flush() # Ensure error print is seen
        traceback.print_exc() # Print the full traceback
        sys.stderr.flush() # Ensure traceback is flushed
        return None

# --- Uploads a local file to GCS ---
def upload_to_gcs(filename):
    if not os.path.exists(filename):
        print(f"[ERROR] File does not exist locally: {filename}. Cannot upload to GCS.")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
        return
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"debug/{filename}")
        print(f"[DEBUG] Attempting GCS upload for {filename} to gs://{BUCKET_NAME}/debug/{filename}")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
        blob.upload_from_filename(filename)
        print(f"Uploaded {filename} to gs://{BUCKET_NAME}/debug/{filename}")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
    except Exception as e:
        print(f"[ERROR] GCS upload failed for {filename}: {e}")
        sys.stdout.flush() # Ensure error print is seen
        traceback.print_exc() # Print the full traceback
        sys.stderr.flush() # Ensure traceback is flushed
    finally:
        # Clean up local file after upload attempt
        try:
            if os.path.exists(filename):
                os.remove(filename)
                print(f"Deleted local screenshot file: {filename}")
                sys.stdout.flush() # Ensure this print is seen
                sys.stderr.flush() # Ensure this print is seen
        except Exception as e:
            print(f"Failed to delete local file {filename}: {e}")
            sys.stdout.flush() # Ensure error print is seen
            sys.stderr.flush() # Ensure error print is seen

# --- Main workflow ---
def login_and_capture():
    print(f"[DEBUG] Starting screenshot job. GCS Bucket: {BUCKET_NAME}")
    sys.stdout.flush() # Ensure this print is seen
    sys.stderr.flush() # Ensure this print is seen

    if not test_gcs_upload():
        print("[ERROR] GCS connectivity test failed. Aborting script as GCS is required.")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
        return

    print("[DEBUG] Attempting to initialize WebDriver...")
    sys.stdout.flush() # Ensure this print is seen
    sys.stderr.flush() # Ensure this print is seen
    driver = None # Initialize driver to None for finally block
    try:
        driver = init_driver()
        print("[DEBUG] WebDriver initialized successfully.")
        sys.stdout.flush() # Ensure this print is seen
        sys.stderr.flush() # Ensure this print is seen
    except Exception as e:
        print(f"[ERROR] Failed to initialize WebDriver: {e}")
        sys.stdout.flush() # Ensure error print is seen
        traceback.print_exc() # Print the full traceback
        sys.stderr.flush() # Ensure traceback is flushed
        # --- Check for both Chrome and Chromedriver logs here ---
        if os.path.exists("/tmp/chrome_debug_python.log"):
            print("--- Contents of /tmp/chrome_debug_python.log after init failure ---")
            sys.stdout.flush() ; sys.stderr.flush()
            with open("/tmp/chrome_debug_python.log", "r") as f:
                print(f.read())
            sys.stdout.flush() ; sys.stderr.flush()
            print("--- End contents of /tmp/chrome_debug_python.log ---")
            sys.stdout.flush() ; sys.stderr.flush()
        else:
            print("No /tmp/chrome_debug_python.log found.")
            sys.stdout.flush() ; sys.stderr.flush()

        if os.path.exists("/tmp/chromedriver_debug.log"):
            print("--- Contents of /tmp/chromedriver_debug.log after init failure ---")
            sys.stdout.flush() ; sys.stderr.flush()
            with open("/tmp/chromedriver_debug.log", "r") as f:
                print(f.read())
            sys.stdout.flush() ; sys.stderr.flush()
            print("--- End contents of /tmp/chromedriver_debug.log ---")
            sys.stdout.flush() ; sys.stderr.flush()
        else:
            print("No /tmp/chromedriver_debug.log found.")
            sys.stdout.flush() ; sys.stderr.flush()
        
        return # Abort if driver fails to init

    wait = WebDriverWait(driver, 15)

    try:
        print("[DEBUG] Navigating to login page...")
        sys.stdout.flush() ; sys.stderr.flush()
        driver.get("https://clients.hireintelligence.io/login")
        filename = take_debug_screenshot(driver, "login_page_loaded")
        if filename:
            upload_to_gcs(filename)

        username = os.environ.get("HIRE_USERNAME")
        password = os.environ.get("HIRE_PASSWORD")
        print(f"[DEBUG] Using username: {username}") # Consider masking username in production
        sys.stdout.flush() ; sys.stderr.flush()

        wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]"))).click()
        print("[DEBUG] Submitted login form.")
        sys.stdout.flush() ; sys.stderr.flush()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Jobs Listed')]")))
        print("[DEBUG] Dashboard loaded.")
        sys.stdout.flush() ; sys.stderr.flush()
        filename = take_debug_screenshot(driver, "dashboard_loaded")
        if filename:
            upload_to_gcs(filename)

        print("[DEBUG] Navigating to Multi-Candidate View...")
        sys.stdout.flush() ; sys.stderr.flush()
        multi_view_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(),'Multi-Candidate View')]")))
        multi_view_button.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Candidate Tracker')]")))
        print("[DEBUG] Multi-candidate view loaded.")
        sys.stdout.flush() ; sys.stderr.flush()
        filename = take_debug_screenshot(driver, "multi_candidate_view")
        if filename:
            upload_to_gcs(filename)

    except TimeoutException as e:
        print("[ERROR] Timeout waiting for page element:", e)
        sys.stdout.flush() ; sys.stderr.flush()
        traceback.print_exc()
        sys.stdout.flush() ; sys.stderr.flush()
        filename = take_debug_screenshot(driver, "timeout_error") # Take error screenshot
        if filename:
            upload_to_gcs(filename)
    except Exception as e:
        print("[ERROR] Unexpected error:", e)
        sys.stdout.flush() ; sys.stderr.flush()
        traceback.print_exc()
        sys.stdout.flush() ; sys.stderr.flush()
        filename = take_debug_screenshot(driver, "unexpected_error") # Take error screenshot
        if filename:
            upload_to_gcs(filename)
    finally:
        if driver: # Ensure driver exists before quitting
            print("[DEBUG] Closing browser.")
            sys.stdout.flush() ; sys.stderr.flush()
            driver.quit()
        else:
            print("[DEBUG] Driver not initialized, no browser to close.")
            sys.stdout.flush() ; sys.stderr.flush()


if __name__ == "__main__":
    login_and_capture()
