from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Setup
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 30)

# Step 1 – Login
driver.get("https://clients.hireintelligence.io/")
wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys("crootonmaster@applygateway.com")
driver.find_element(By.NAME, "password").send_keys("YOUR_PASSWORD")  # Update securely
driver.find_element(By.XPATH, "//button[text()='Log In']").click()

# Step 2 – Wait for "Jobs Listed" text
wait.until(EC.text_to_be_present_in_element(
    (By.XPATH, "//div[contains(text(), 'Jobs Listed')]"),
    "Jobs Listed"
))

# Step 3 – Go to Multi-Candidate Admin page
driver.execute_script("window.location.href='https://clients.hireintelligence.io/multi-candidate-admin'")

# Step 4 – Wait for All [XX] to appear
wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(text(), 'All [')]")))

# At this point the target page is fully loaded
print("✅ Multi-Candidate Admin page loaded successfully!")

# Optional: Debug Screenshot
driver.save_screenshot("/tmp/admin_page_loaded.png")

# Cleanup
driver.quit()
