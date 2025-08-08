import os
import time
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load credentials from environment
USERNAME = os.getenv("HIRE_USERNAME")
PASSWORD = os.getenv("HIRE_PASSWORD")
LOGIN_URL = "https://clients.hireintelligence.io/"
CANDIDATE_URL = "https://clients.hireintelligence.io/candidates"
BUCKET_NAME = os.getenv("CV_BUCKET_NAME", "intelligent-recruitment-cvs")

def start_browser():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    driver = uc.Chrome(options=options)
    return driver

def login(driver):
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "email")))

    driver.find_element(By.ID, "email").send_keys(USERNAME)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, '//button[contains(text(), "Login")]').click()

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Jobs Listed")]'))
    )
    print("✅ Logged in successfully.")

def fetch_candidates(driver):
    driver.get(CANDIDATE_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "table")))

    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
    print(f"📄 Found {len(rows)} candidate rows.")
    data = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 4:
            data.append({
                "name": cols[0].text.strip(),
                "email": cols[1].text.strip(),
                "job_ref_number": cols[2].text.strip(),
                "created_on": cols[3].text.strip()
            })
    return pd.DataFrame(data)

def save_and_upload(df):
    if df.empty:
        print("⚠️ No candidate data found.")
        return
    filename = f"hi_candidates_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    df.to_excel(filename, index=False)
    print(f"💾 Saved: {filename}")

    # Upload to GCS
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"reports/{filename}")
    blob.upload_from_filename(filename)
    print(f"✅ Uploaded to GCS: {BUCKET_NAME}/reports/{filename}")

def main():
    driver = start_browser()
    try:
        login(driver)
        df = fetch_candidates(driver)
        save_and_upload(df)
    except Exception as e:
        print("❌ Error:", e)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
