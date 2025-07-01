# --- Initializes the Selenium WebDriver ---
def init_driver():
    chrome_options = Options()
    # No --headless=new (Selenium image handles display)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu') # Good practice for headless
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-path=/tmp/chrome_debug_python.log') # Chrome's own logs

    # --- CRITICAL CHANGES FOR selenium/standalone-chrome BASE IMAGE ---
    # REMOVE binary_location - Selenium image manages Chrome's path
    # chrome_options.binary_location = "/opt/chrome/chrome"

    print("[DEBUG] Initializing headless Chrome WebDriver...")
    
    # Use Service() without explicit path, and add verbose ChromeDriver logging
    service = Service(log_path="/tmp/chromedriver_debug.log", verbose=True) 

    return webdriver.Chrome(service=service, options=chrome_options)
