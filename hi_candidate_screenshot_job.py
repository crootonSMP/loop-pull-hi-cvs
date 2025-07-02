from google.cloud import storage
from PIL import Image
from io import BytesIO
import uuid

def upload_to_gcs(bucket_name: str, image_data: bytes, destination_path: str) -> None:
    """Upload screenshot to Google Cloud Storage"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        
        with BytesIO(image_data) as image_stream:
            blob.upload_from_file(image_stream, content_type='image/png')
        
        logger.info(f"Screenshot uploaded to gs://{bucket_name}/{destination_path}")
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {str(e)}")
        raise

def capture_and_upload_screenshot(driver: webdriver.Chrome, url: str, bucket_name: str, description: str) -> None:
    """Navigate to URL, capture screenshot, and upload to GCS"""
    try:
        logger.info(f"Navigating to {url}")
        driver.get(url)
        
        # Special handling for login page
        if "login" in url:
            logger.info("Performing login...")
            WebDriverWait(driver, config.explicit_wait).until(
                EC.presence_of_element_located((By.NAME, "email"))
            ).send_keys(config.username)
            
            driver.find_element(By.NAME, "password").send_keys(config.password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(3)  # Wait for login to complete
        
        # Special handling for jobs page
        if url == "https://clients.hireintelligence.io/":
            logger.info("Waiting for jobs count...")
            WebDriverWait(driver, config.explicit_wait).until(
                EC.text_to_be_present_in_element(
                    (By.XPATH, "//*[contains(text(), 'Jobs Listed')]"),
                    "Jobs Listed"
                )
            )
        
        # Capture screenshot
        screenshot = driver.get_screenshot_as_png()
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{description.replace(' ', '_')}_{timestamp}_{str(uuid.uuid4())[:8]}.png"
        gcs_path = f"screenshots/{filename}"
        
        # Upload to GCS
        upload_to_gcs(bucket_name, screenshot, gcs_path)
        
    except Exception as e:
        logger.error(f"Failed to capture {url}: {str(e)}")
        raise

def main() -> int:
    driver = None
    try:
        config = Config().validate()
        logger.info(f"Starting job with configuration: {config}")
        
        driver = setup_driver(config)
        bucket_name = "recruitment-engine-cvs-sp-260625"
        
        # Capture jobs dashboard screenshot
        capture_and_upload_screenshot(
            driver,
            "https://clients.hireintelligence.io/login",  # Will handle login
            bucket_name,
            "jobs_dashboard"
        )
        
        # Capture multi-candidate admin screenshot
        capture_and_upload_screenshot(
            driver,
            "https://clients.hireintelligence.io/multi-candidate-admin",
            bucket_name,
            "multi_candidate_admin"
        )
        
        logger.info("All screenshots captured and uploaded successfully")
        return 0
        
    except Exception as e:
        logger.critical(f"Job failed: {str(e)}", exc_info=True)
        return 1
    finally:
        cleanup_driver(driver)
