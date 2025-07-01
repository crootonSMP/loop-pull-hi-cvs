FROM python:3.11-slim

# Install Chromium and ChromeDriver dependencies
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg ca-certificates fonts-liberation libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 \
    libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    xdg-utils libgbm1 libgtk-3-0 libxshmfence1 libxi6 libxcursor1 libxss1 \
    chromium chromium-driver

# Set up Chrome paths explicitly
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script
COPY scrape_cv_links.py .

# Run the script
CMD ["python", "scrape_cv_links.py"]
