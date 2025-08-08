FROM python:3.11-bookworm

ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install dependencies for Chrome + Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip curl gnupg2 ca-certificates fonts-liberation libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 xdg-utils libu2f-udev libvulkan1 && \
    rm -rf /var/lib/apt/lists/*

# ✅ Install Chrome v117.0.5938.92
RUN wget https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_117.0.5938.92-1_amd64.deb && \
    apt install -y ./google-chrome-stable_117.0.5938.92-1_amd64.deb && \
    rm google-chrome-stable_117.0.5938.92-1_amd64.deb

# ✅ Install matching ChromeDriver
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/117.0.5938.92/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip

# Create non-root user
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser/app

# Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your script
COPY --chown=appuser:appuser daily_CV_and_candidate_importer.py .

ENTRYPOINT ["python", "daily_CV_and_candidate_importer.py"]
