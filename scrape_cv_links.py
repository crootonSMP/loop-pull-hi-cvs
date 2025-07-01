from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import traceback

EMAIL = "crootonmaster@applygateway.com"
PASSWORD = "YOUR_PASSWORD"

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 40)

try:
    print("🔍 Loading login page...")
    driver.get("https://clients.hireintelligence.io/")
    time.sleep(2)
    driver.save_screenshot("/tmp/loaded_login.png")  # EARLY SCREENSHOT

    print("🔐 Filling login form...")
    wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()

    print("⏳ Waiting for dashboard (Jobs Listed)...")
    wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Jobs Listed')]")))
    driver.save_screenshot("/tmp/after_login.png")
    print("✅ Dashboard loaded!")

    print("➡️ Navigating to candidate admin page...")
    driver.execute_script("window.location.href = 'https://clients.hireintelligence.io/multi-candidate-admin'")

    print("⏳ Waiting for candidate admin to show All [")
    wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(text(), 'All [')]")))
    driver.save_screenshot("/tmp/final_admin_page.png")
    print("✅ Multi-candidate admin page ready!")

except Exception as e:
    print("❌ FAILED with exception:")
    traceback.print_exc()
    driver.save_screenshot("/tmp/failure.png")
    raise

finally:
    driver.quit()
