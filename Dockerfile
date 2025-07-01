FROM ghcr.io/puppeteer/puppeteer:latest

# Optional: Set timezone
ENV TZ=Europe/London

# Copy your Node.js app and install dependencies
COPY package*.json ./
RUN npm install

COPY . .

# Run your Node.js script
CMD ["node", "hi_candidate_screenshot_job.js"]
