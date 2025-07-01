{
  "name": "puppeteer-automation",
  "version": "1.0.0",
  "description": "Headless Chrome automation with Puppeteer on Cloud Run",
  "main": "index.js",
  "scripts": {
    "start": "node index.js"
  },
  "dependencies": {
    "puppeteer": "^22.0.0",
    "@google-cloud/storage": "^7.0.0" 
    
    // Using a specific, recent Puppeteer version is good.
    // @google-cloud/storage is needed for GCS integration from Node.js
  }
}
