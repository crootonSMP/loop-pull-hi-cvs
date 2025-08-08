FROM python:3.11-bookworm

ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip curl gnupg2 ca-certificates fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 xdg-utils libu2f-udev libvulkan1 && \
    rm -rf /var/lib/apt/lists/*

# ✅ Install current stable Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# ✅ Install matching ChromeDriver for Chrome 116.0.5845.96
RUN CHROMEDRIVER_VERSION="116.0.5845.96" && \
    wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip

# Create non-root user
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser/app

# Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script
COPY --chown=appuser:appuser daily_CV_and_candidate_importer.py .

# Run script
ENTRYPOINT ["python", "daily_CV_and_candidate_importer.py"]
