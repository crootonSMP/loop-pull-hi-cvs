import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage

# GCS Setup
BUCKET_NAME = "recruitment-engine-cvs-sp-260625"
client = storage.Client()
bucket = client.bucket(BUCKET_NAME)

def upload_to_gcs(local_path, gcs_path):
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    print(f"📤 Uploaded {gcs_path}")

# Credentials
EMAIL = os.environ["LOGIN_EMAIL"]
PASSWORD = os.environ["HIRE_PASSWORD"]

# Chrome Driver Setup
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    # Step 1: Load login page
    print("➡️ Opening login page...")
    driver.get("https://clients.hireintelligence.io/login")
    wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, '//button[contains(text(), "Login")]').click()
    print("✅ Login submitted")
    
    # Wait for dashboard to show job count
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Jobs Listed")]')))
    time.sleep(2)  # Allow iframe updates
    driver.save_screenshot("/tmp/after_login.png")
    upload_to_gcs("/tmp/after_login.png", "debug/after_login.png")

    # Step 2: Navigate to multi-candidate admin
    print("➡️ Navigating to multi-candidate-admin page")
    driver.execute_script('window.location = "https://clients.hireintelligence.io/multi-candidate-admin";')
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "All [") or contains(text(), "All [0")]')))
    time.sleep(2)
    driver.save_screenshot("/tmp/multi_admin_loaded.png")
    upload_to_gcs("/tmp/multi_admin_loaded.png", "debug/multi_admin_loaded.png")

    # (Optional: Further scraping logic goes here)

    print("✅ Navigation and page load confirmed")

except Exception as e:
    print("❌ Error during login or navigation:", str(e))
    driver.save_screenshot("/tmp/error.png")
    upload_to_gcs("/tmp/error.png", "debug/error.png")

    # Save full HTML for debugging
    with open("/tmp/page.html", "w") as f:
        f.write(driver.page_source)
    upload_to_gcs("/tmp/page.html", "debug/page.html")
    raise

finally:
    driver.quit()
