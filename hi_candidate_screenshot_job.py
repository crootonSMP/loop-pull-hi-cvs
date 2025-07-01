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
    # Keep these, as they are still useful even with Xvfb
    chrome_options.add_argument('--headless=new') # Although Xvfb provides a virtual display, this keeps it internally headless
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    # Add Python-level Chrome logging for more info if it crashes later
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log')

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    
    # Specify the executable_path to run Chrome via xvfb-run
    # No need to use Service() here as we are providing executable_path directly
    # and chromedriver is expected to be in PATH or located by Selenium.
    driver = webdriver.Chrome(
        executable_path="/usr/bin/chromedriver", # ChromeDriver is in /usr/bin/
        options=chrome_options,
        # This is the command that will actually start Chrome via Xvfb
        # Xvfb: run a command in a new X server display
        # :99: arbitrary display number
        # -ac: disable access control
        # -screen 0 1920x1080x24: screen resolution and color depth
        # n: do not fork, stay in foreground
        # -- : end of xvfb-run options
        # /opt/chrome/chrome: path to the actual Chrome binary
        service=Service(executable_path="/usr/bin/chromedriver") # Keep service for WebDriver.Chrome
    )
    
    # We need to explicitly set the binary location if we're also using xvfb-run as the executable.
    # The combination of `executable_path` and `service` with `binary_location` can be tricky.
    # Let's try specifying binary_location for Chrome if we are running it via Xvfb.
    # Selenium 4 generally uses Service for the driver and then options for the browser itself.
    # Let's adjust for Xvfb and explicit binary path for the browser:

    chrome_options.binary_location = "/opt/chrome/chrome" # Tell Selenium where the actual Chrome binary is

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
