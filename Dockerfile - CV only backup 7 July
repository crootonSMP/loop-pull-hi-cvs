# Use the official Python image as base RESH
FROM python:3.10-slim

# Install Chrome and Chromedriver using Chrome for Testing
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and Chromedriver from stable channel
RUN CHROME_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && echo "Installing Chrome $CHROME_VERSION" \
    && wget -q --tries=3 --retry-connrefused \
       "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION/linux64/chrome-linux64.zip" -O /tmp/chrome.zip \
    && unzip /tmp/chrome.zip -d /opt \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && wget -q --tries=3 --retry-connrefused \
       "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chrome.zip /tmp/chromedriver*

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libxss1 \
    libcups2 \
    libdbus-glib-1-2 \
    libxtst6 \
    libxrender1 \
    libxi6 \
    xvfb \
    fonts-liberation \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure shared memory
RUN mkdir -p /dev/shm && chmod 1777 /dev/shm

# Environment variables
ENV CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    DISPLAY=:99 \
    SCREEN_WIDTH=1920 \
    SCREEN_HEIGHT=1080 \
    SE_SHM_SIZE="2g" \
    PATH="/app/.local/bin:$PATH"

# Create non-root user
RUN groupadd -r scraper && \
    useradd -r -g scraper -d /app -s /bin/bash scraper && \
    mkdir -p /app && \
    chown -R scraper:scraper /app

WORKDIR /app
USER scraper

# Install Python dependencies
COPY --chown=scraper:scraper requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=scraper:scraper . .

CMD ["python", "hi_cv_downloader.py"]
