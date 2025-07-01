const puppeteer = require('puppeteer');

async function runAutomation() {
    let browser;
    try {
        console.log('[DEBUG] Launching browser...');
        browser = await puppeteer.launch({
            headless: 'new', // Use the new headless mode
            args: [
                '--no-sandbox', // Essential for Docker
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage', // Recommended for Docker
                '--disable-gpu', // Recommended for Docker
                '--window-size=1920,1080' // Set a consistent window size
            ]
        });
        const page = await browser.newPage();

        // Set a default timeout for navigation and element interactions
        page.setDefaultNavigationTimeout(60000); // 60 seconds
        page.setDefaultTimeout(30000); // 30 seconds for element interactions

        // --- GCS Test (similar to your Python version) ---
        console.log('[DEBUG] Running GCS test (Puppeteer does not directly upload to GCS. This is placeholder).');
        // For GCS, you'd use @google-cloud/storage Node.js client library
        // const { Storage } = require('@google-cloud/storage');
        // const storage = new Storage();
        // const bucketName = process.env.DEBUG_SCREENSHOT_BUCKET || 'your-gcs-bucket';
        // const bucket = storage.bucket(bucketName);
        // const blob = bucket.file(`debug_test/puppeteer_test_${Date.now()}.txt`);
        // await blob.save('Puppeteer GCS test successful!');
        console.log('[DEBUG] GCS test placeholder complete.');
        // --- End GCS Test ---


        console.log('[DEBUG] Navigating to login page...');
        await page.goto('https://clients.hireintelligence.io/login', { waitUntil: 'networkidle2' }); // Wait for network to be idle

        // Login
        const username = process.env.HIRE_USERNAME;
        const password = process.env.HIRE_PASSWORD;
        console.log(`[DEBUG] Using username: ${username}`); // Be cautious with logging credentials

        await page.type('#email', username); // Type into email field
        await page.type('#password', password); // Type into password field
        await page.click('button[type="submit"], button:contains("Sign In")'); // Click sign in button

        console.log('[DEBUG] Login submitted. Waiting for dashboard...');
        await page.waitForSelector('div:text("Jobs Listed")', { timeout: 30000 }); // Wait for "Jobs Listed" text
        console.log('[DEBUG] Dashboard loaded.');

        // Take screenshot (Puppeteer's way)
        const screenshotPath = `/tmp/dashboard_${Date.now()}.png`;
        await page.screenshot({ path: screenshotPath, fullPage: true });
        console.log(`[DEBUG] Screenshot saved locally to: ${screenshotPath}`);

        // --- Upload screenshot to GCS (requires @google-cloud/storage) ---
        // const { Storage } = require('@google-cloud/storage');
        // const storage = new Storage();
        // const bucketName = process.env.DEBUG_SCREENSHOT_BUCKET || 'your-gcs-bucket';
        // const bucket = storage.bucket(bucketName);
        // const blob = bucket.file(`debug/${path.basename(screenshotPath)}`);
        // await bucket.upload(screenshotPath, { destination: `debug/${path.basename(screenshotPath)}` });
        // console.log(`[DEBUG] Screenshot uploaded to GCS: gs://${bucketName}/debug/${path.basename(screenshotPath)}`);
        // --- End GCS Upload ---

        console.log('[DEBUG] Navigating to Multi-Candidate View...');
        await page.click('button:text("Multi-Candidate View")'); // Click Multi-Candidate View button
        await page.waitForSelector('div:text("Candidate Tracker")', { timeout: 30000 }); // Wait for "Candidate Tracker" text
        console.log('[DEBUG] Multi-candidate view loaded.');

        const multiViewScreenshotPath = `/tmp/multi_candidate_view_${Date.now()}.png`;
        await page.screenshot({ path: multiViewScreenshotPath, fullPage: true });
        console.log(`[DEBUG] Screenshot saved locally to: ${multiViewScreenshotPath}`);
        // Upload to GCS similarly

    } catch (error) {
        console.error('[ERROR] Automation failed:', error);
        if (browser) {
            const errorScreenshotPath = `/tmp/error_${Date.now()}.png`;
            await browser.newPage().then(async (page) => { // Create a new page just for error screenshot
                await page.screenshot({ path: errorScreenshotPath, fullPage: true });
                console.log(`[ERROR] Error screenshot saved to: ${errorScreenshotPath}`);
            }).catch(e => console.error('Failed to take error screenshot:', e));
        }
        process.exit(1); // Exit with a non-zero code on error
    } finally {
        if (browser) {
            console.log('[DEBUG] Closing browser.');
            await browser.close();
        }
    }
}

runAutomation();
