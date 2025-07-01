import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EMAIL = os.environ["HIRE_USERNAME"]
PASSWORD = os.environ["HIRE_PASSWORD"]

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 30)

try:
    driver.get("https://clients.hireintelligence.io/login")
    
    wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(EMAIL)
    wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(PASSWORD)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Login')]"))).click()
    
    print("🔐 Login submitted")

    # Wait until the main jobs dashboard has loaded (e.g., wait for "Jobs Listed")
    wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Jobs Listed')]")))

    print("✅ Login successful and dashboard loaded")

    # DEBUG screenshot
    driver.save_screenshot("/tmp/after_login.png")

except Exception as e:
    print("❌ Error during login or load:", e)
    driver.save_screenshot("/tmp/error.png")

finally:
    driver.quit()
