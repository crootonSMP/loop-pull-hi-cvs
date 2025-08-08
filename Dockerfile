FROM python:3.11-slim-bookworm

# Set timezone
ENV TZ=Europe/London
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip curl gnupg2 ca-certificates fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils libu2f-udev libvulkan1 chromium \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_DRIVER_VERSION=$(curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip

# Create user
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser/app

# Copy and install Python packages
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY --chown=appuser:appuser daily_CV_and_candidate_importer.py .

# Entrypoint
ENTRYPOINT ["python", "daily_CV_and_candidate_importer.py"]
