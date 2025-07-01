const puppeteer = require('puppeteer');
const { Storage } = require('@google-cloud/storage'); // For GCS interaction
const storage = new Storage(); // Initialize GCS client

async function runAutomation() {
    let browser;
    try {
        console.log('[DEBUG] Launching browser...');
        // Puppeteer launches Chromium. These args are crucial for Docker/headless.
        browser = await puppeteer.launch({
            headless: 'new', // Use the new headless mode (more stable)
            args: [
                '--no-sandbox', // CRITICAL for Docker environments
                '--disable-setuid-sandbox', // CRITICAL for Docker environments
                '--disable-dev-shm-usage', // Recommended to avoid /dev/shm issues in Docker
                '--disable-gpu', // Recommended for headless
                '--window-size=1920,1080', // Consistent window size
                '--single-process', // Can help in constrained environments
                '--no-zygote' // Another option for constrained envs
            ]
        });
        const page = await browser.newPage();

        // Set default timeouts for navigation and element interactions
        page.setDefaultNavigationTimeout(60000); // 60 seconds for page loads
        page.setDefaultTimeout(30000); // 30 seconds for element wait/interaction

        // --- GCS Connectivity Test (Node.js version) ---
        const bucketName = process.env.DEBUG_SCREENSHOT_BUCKET || 'recruitment-engine-cvs-sp-260625';
        console.log(`[DEBUG] Attempting GCS connectivity test. Bucket: ${bucketName}`);
        try {
            const testFilename = `debug_test/puppeteer_test_${Date.now()}.txt`;
            const bucket = storage.bucket(bucketName);
            const blob = bucket.file(testFilename);
            await blob.save(`This is a test file uploaded from Puppeteer on Cloud Run at ${new Date().toISOString()}.`);
            console.log(`[DEBUG] Successfully uploaded GCS test file: gs://${bucketName}/${testFilename}`);
        } catch (gcsError) {
            console.error('[ERROR] GCS connectivity test failed:', gcsError);
            console.error('Please ensure the Cloud Run service account has Storage Object Creator role on the bucket.');
            process.exit(1); // Exit if GCS fails, as screenshots won't work
        }
        // --- End GCS Test ---

        console.log('[DEBUG] Navigating to login page...');
        await page.goto('https://clients.hireintelligence.io/login', { waitUntil: 'networkidle2' });

        // Login credentials from environment variables
        const username = process.env.HIRE_USERNAME;
        const password = process.env.HIRE_PASSWORD;
        console.log(`[DEBUG] Using username: ${username ? 'retrieved_from_env' : 'NOT_SET'}`); // Avoid logging actual username

        if (!username || !password) {
            console.error('[ERROR] HIRE_USERNAME or HIRE_PASSWORD environment variables are not set.');
            process.exit(1);
        }

        // Type into fields and click button
        await page.type('#email', username);
        await page.type('#password', password);
        await page.click('button[type="submit"], button:text("Sign In")'); // Target by type or text

        console.log('[DEBUG] Login submitted. Waiting for dashboard...');
        await page.waitForSelector('div:text("Jobs Listed")', { timeout: 30000 }); // Wait for element with text "Jobs Listed"
        console.log('[DEBUG] Dashboard loaded.');

        // Take dashboard screenshot
        const dashboardScreenshotFilename = `dashboard_${Date.now()}.png`;
        const dashboardScreenshotPath = `/tmp/${dashboardScreenshotFilename}`;
        await page.screenshot({ path: dashboardScreenshotPath, fullPage: true });
        console.log(`[DEBUG] Screenshot saved locally: ${dashboardScreenshotPath}`);
        await storage.bucket(bucketName).upload(dashboardScreenshotPath, { destination: `debug/${dashboardScreenshotFilename}` });
        console.log(`[DEBUG] Screenshot uploaded to GCS: gs://${bucketName}/debug/${dashboardScreenshotFilename}`);
        // Clean up local screenshot
        await require('fs/promises').unlink(dashboardScreenshotPath);


        console.log('[DEBUG] Navigating to Multi-Candidate View...');
        await page.click('button:text("Multi-Candidate View")'); // Click button with text "Multi-Candidate View"
        await page.waitForSelector('div:text("Candidate Tracker")', { timeout: 30000 }); // Wait for element with text "Candidate Tracker"
        console.log('[DEBUG] Multi-candidate view loaded.');

        // Take multi-candidate view screenshot
        const multiViewScreenshotFilename = `multi_candidate_view_${Date.now()}.png`;
        const multiViewScreenshotPath = `/tmp/${multiViewScreenshotFilename}`;
        await page.screenshot({ path: multiViewScreenshotPath, fullPage: true });
        console.log(`[DEBUG] Screenshot saved locally: ${multiViewScreenshotPath}`);
        await storage.bucket(bucketName).upload(multiViewScreenshotPath, { destination: `debug/${multiViewScreenshotFilename}` });
        console.log(`[DEBUG] Screenshot uploaded to GCS: gs://${bucketName}/debug/${multiViewScreenshotFilename}`);
        // Clean up local screenshot
        await require('fs/promises').unlink(multiViewScreenshotPath);


    } catch (error) {
        console.error('[ERROR] Automation failed:', error);
        if (browser) {
            console.log('[DEBUG] Attempting to take error screenshot...');
            try {
                // Ensure the page context is available for screenshot, or create a new one
                const errorPage = browser.newPage ? await browser.newPage() : page;
                const errorScreenshotFilename = `error_${Date.now()}.png`;
                const errorScreenshotPath = `/tmp/${errorScreenshotFilename}`;
                await errorPage.screenshot({ path: errorScreenshotPath, fullPage: true });
                console.error(`[ERROR] Error screenshot saved locally: ${errorScreenshotPath}`);
                // Upload error screenshot
                const bucketName = process.env.DEBUG_SCREENSHOT_BUCKET || 'recruitment-engine-cvs-sp-260625';
                await storage.bucket(bucketName).upload(errorScreenshotPath, { destination: `debug/${errorScreenshotFilename}` });
                console.error(`[ERROR] Error screenshot uploaded to GCS: gs://${bucketName}/debug/${errorScreenshotFilename}`);
                await require('fs/promises').unlink(errorScreenshotPath);
            } catch (screenshotError) {
                console.error('[ERROR] Failed to take/upload error screenshot:', screenshotError);
            }
        }
        process.exit(1); // Exit with a non-zero code on error
    } finally {
        if (browser) {
            console.log('[DEBUG] Closing browser.');
            await browser.close();
        }
    }
}

// Ensure the automation runs when the script is executed
runAutomation();
