from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

EMAIL = "crootonmaster@applygateway.com"
PASSWORD = "YOUR_PASSWORD"  # Inject securely in production

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 30)

try:
    # Step 1 – Go to login page
    driver.get("https://clients.hireintelligence.io/")
    wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()

    # Step 2 – Wait until redirected to dashboard
    wait.until(EC.url_contains("/"))
    wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Jobs Listed')]")))

    print("✅ Logged in and on main dashboard page")

    # Step 3 – Navigate manually to multi-candidate-admin
    driver.execute_script("window.location.href = 'https://clients.hireintelligence.io/multi-candidate-admin'")
    
    # Step 4 – Wait until admin table loads (e.g., All [69])
    wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(text(), 'All [')]")))
    print("✅ Multi-Candidate Admin loaded successfully!")

    # Debug screenshot
    driver.save_screenshot("/tmp/page_success.png")

except Exception as e:
    print("❌ Error:", e)
    driver.save_screenshot("/tmp/failure.png")
    raise

finally:
    driver.quit()
