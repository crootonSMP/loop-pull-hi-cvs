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
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu') # Still good practice for headless
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    # Add Python-level Chrome logging for more info if it crashes later
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')
    
    # --- CRITICAL CHANGE FOR XVFB ---
    # Tell Selenium to use the Chrome binary *wrapped by xvfb-run*
    chrome_options.binary_location = "/usr/bin/xvfb-run" 
    chrome_options.add_argument("-a") # xvfb-run: automatically pick a free display
    chrome_options.add_argument("-s") # xvfb-run: arguments for Xvfb itself
    chrome_options.add_argument("-screen") # xvfb-run: arguments for Xvfb itself
    chrome_options.add_argument("0") # xvfb-run: arguments for Xvfb itself
    chrome_options.add_argument("1920x1080x24") # xvfb-run: arguments for Xvfb itself
    chrome_options.add_argument("--") # xvfb-run: separator between xvfb-run options and the command to run
    chrome_options.add_argument("/opt/chrome/chrome") # The actual Chrome binary path

    # Remove --headless=new when using xvfb, as Xvfb provides the display.
    # While Chrome internally still can be headless, it's often simpler to let Xvfb manage the display.
    # If it fails, you can try re-adding '--headless=new' to chrome_options.add_argument()
    # but for now, let's remove it for Xvfb integration clarity.
    # chrome_options.argument('--headless=new') # Removed for Xvfb

    print("[DEBUG] Initializing headless Chrome WebDriver with Xvfb...")
    
    service = Service("/usr/bin/chromedriver") # Point to the ChromeDriver executable

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
