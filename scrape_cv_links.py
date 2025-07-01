import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from take_debug_screenshot import take_debug_screenshot

EMAIL = os.environ["HIRE_USERNAME"]
PASSWORD = os.environ["HIRE_PASSWORD"]

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    print("➡️ Opening login page...")
    driver.get("https://clients.hireintelligence.io/login")
    take_debug_screenshot(driver, "01_login_page_loaded")

    # Login form is directly in DOM, no iframe
    wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(EMAIL)
    wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(PASSWORD)
    driver.find_element(By.XPATH, '//button[contains(text(), "Log In")]').click()
    print("✅ Login submitted")
    take_debug_screenshot(driver, "02_login_submitted")

    # Wait for the dashboard text (e.g., "Jobs Listed") to appear
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Jobs Listed")]')))
    print("🎉 Logged in successfully and landed on dashboard.")
    take_debug_screenshot(driver, "03_dashboard_loaded")

except Exception as e:
    print("❌ Error during login or navigation:", e)
    take_debug_screenshot(driver, "error_occurred")

finally:
    driver.quit()
