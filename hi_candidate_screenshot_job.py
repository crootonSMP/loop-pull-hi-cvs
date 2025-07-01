import os
import time
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from google.cloud import storage


def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    return webdriver.Chrome(options=chrome_options)


def take_debug_screenshot(driver, step_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{step_name}_{timestamp}.png"
    driver.save_screenshot(filename)
    print(f"Saved screenshot: {filename}")
    upload_to_gcs(filename)


def upload_to_gcs(filename):
    try:
        bucket_name = os.environ.get("DEBUG_SCREENSHOT_BUCKET")
        if not bucket_name:
            print("No GCS bucket defined for screenshot uploads.")
            return

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"debug/{filename}")
        blob.upload_from_filename(filename)
        print(f"Uploaded {filename} to gs://{bucket_name}/debug/{filename}")
    except Exception as e:
        print(f"Failed to upload screenshot to GCS: {e}")
        traceback.print_exc()


def login_and_capture():
    driver = init_driver()
    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://hireintelligence.io")
        take_debug_screenshot(driver, "login_page_loaded")

        username = os.environ.get("HIRE_USERNAME")
        password = os.environ.get("HIRE_PASSWORD")

        wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]"))).click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Jobs Listed')]")))
        take_debug_screenshot(driver, "dashboard_loaded")

        multi_candidate_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(),'Multi-Candidate View')]")))
        multi_candidate_button.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Candidate Tracker')]")))
        take_debug_screenshot(driver, "multi_candidate_view")

    except TimeoutException as e:
        print("Timeout while waiting for page elements:", e)
        traceback.print_exc()
    except Exception as e:
        print("An unexpected error occurred:", e)
        traceback.print_exc()
    finally:
        driver.quit()


if __name__ == "__main__":
    login_and_capture()
