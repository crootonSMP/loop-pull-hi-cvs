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
wait = WebDriverWait(driver, 30)

try:
    print("🔍 Opening login page...")
    driver.get("https://clients.hireintelligence.io/")
    time.sleep(2)
    driver.save_screenshot("/tmp/step1_initial_page.png")

    print("🔐 Trying to find login field...")
    try:
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_field.send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()
        print("✅ Login submitted!")
    except Exception as e:
        print("❌ Login fields not found.")
        driver.save_screenshot("/tmp/step2_login_failed.png")
        with open("/tmp/login_page.html", "w") as f:
            f.write(driver.page_source)
        raise

    print("⏳ Waiting for job page to load...")
    wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Jobs Listed')]")))
    driver.save_screenshot("/tmp/step3_after_login.png")
    print("✅ Login successful!")

    print("➡️ Navigating to multi-candidate admin page...")
    driver.execute_script("window.location.href = 'https://clients.hireintelligence.io/multi-candidate-admin'")
    time.sleep(3)
    driver.save_screenshot("/tmp/step4_candidate_page_loaded.png")

    print("⏳ Waiting for All [number] to appear...")
    wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(text(), 'All [')]")))
    driver.save_screenshot("/tmp/step5_admin_ready.png")
    print("✅ All done!")

except Exception as e:
    print("❌ Full failure caught")
    traceback.print_exc()
    driver.save_screenshot("/tmp/final_error.png")

finally:
    driver.quit()
