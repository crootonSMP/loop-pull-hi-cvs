import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EMAIL = os.environ["LOGIN_EMAIL"]
PASSWORD = os.environ["LOGIN_PASSWORD"]

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
driver.set_window_size(1280, 1024)

try:
    driver.get("https://clients.hireintelligence.io/")
    time.sleep(3)
    driver.save_screenshot("/tmp/01_initial_page.png")

    wait = WebDriverWait(driver, 15)
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.send_keys(EMAIL)
    password_input = driver.find_element(By.NAME, "password")
    password_input.send_keys(PASSWORD)
    login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    login_button.click()

    time.sleep(5)
    driver.save_screenshot("/tmp/02_after_login_click.png")

    # wait for main page to load
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Jobs Listed"))

    driver.save_screenshot("/tmp/03_dashboard_loaded.png")

finally:
    driver.quit()

