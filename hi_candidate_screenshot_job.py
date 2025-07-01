import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

print("[DEBUG] Python script starting (absolute bare minimum).")

try:
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    # No binary_location or explicit Service path needed for selenium/standalone-chrome
    service = Service() 
    driver = webdriver.Chrome(service=service, options=chrome_options)

    print("[DEBUG] WebDriver initialized successfully (bare minimum test).")
    driver.get("about:blank")
    print("[DEBUG] Navigated to about:blank (bare minimum test).")
    driver.quit()
    print("[DEBUG] Browser closed (bare minimum test).")

except Exception as e:
    print(f"[ERROR] Bare minimum WebDriver test failed: {e}")
    import traceback
    traceback.print_exc()

print("[DEBUG] Python script finished (absolute bare minimum).")
