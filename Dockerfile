# Stage 1: Builder - Modernized with security improvements
FROM python:3.10-slim AS builder

# Set build arguments with defaults
ARG TZ=UTC
ARG DEBIAN_FRONTEND=noninteractive
ARG CHROME_VERSION=stable

# System configuration - consolidated ENV
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=${TZ} \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    DISPLAY=:99 \
    SCREEN_WIDTH=1920 \
    SCREEN_HEIGHT=1080 \
    SCREEN_DEPTH=24 \
    DBUS_SESSION_BUS_ADDRESS=/dev/null

# Install system dependencies - optimized for layer caching
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    unzip \
    xvfb \
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
    fonts-liberation \
    libappindicator3-1 \
    libdrm2 \
    libxcomposite1 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create shared memory directory with proper permissions
RUN mkdir -p /dev/shm && chmod 1777 /dev/shm

# Install Chrome and Chromedriver using Chrome for Testing
RUN wget -q -O /tmp/chrome.deb \
    "https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-${CHROME_VERSION}_current_amd64.deb" \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && wget -q -O /tmp/chromedriver.zip \
    "https://chromedriver.storage.googleapis.com/$(google-chrome --version | cut -d ' ' -f3)/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# Verify installations
RUN google-chrome --version && chromedriver --version

# Stage 2: Runtime - Security hardened
FROM python:3.10-slim

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
    fonts-liberation \
    libappindicator3-1 \
    libdrm2 \
    libxcomposite1 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create shared memory directory with proper permissions
RUN mkdir -p /dev/shm && chmod 1777 /dev/shm

# Copy only the minimal required files from builder
COPY --from=builder /usr/bin/google-chrome /usr/bin/
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/
COPY --from=builder /usr/lib/x86_64-linux-gnu/ /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/share/fonts /usr/share/fonts
COPY --from=builder /etc/fonts /etc/fonts

# Environment variables - security focused
ENV CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    CHROME_USER_DATA_DIR=/tmp/chrome-profile \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DISPLAY=:99 \
    SCREEN_WIDTH=1920 \
    SCREEN_HEIGHT=1080 \
    SCREEN_DEPTH=24 \
    DBUS_SESSION_BUS_ADDRESS=/dev/null \
    SE_SHM_SIZE="2g" \
    PATH="/home/scraper/.local/bin:$PATH"

# Create secure non-root user environment
RUN groupadd -r scraper && \
    useradd -r -g scraper -d /app -s /bin/bash scraper && \
    mkdir -p /app && \
    chown -R scraper:scraper /app && \
    mkdir -p "${CHROME_USER_DATA_DIR}" && \
    chown -R scraper:scraper "${CHROME_USER_DATA_DIR}" && \
    chmod 1777 /tmp

WORKDIR /app
USER scraper

# Install Python dependencies with proper numpy/pandas compatibility
COPY --chown=scraper:scraper requirements.txt .
RUN pip install --user --no-cache-dir numpy==1.24.4 && \
    pip install --user --no-cache-dir -r requirements.txt

# Copy application code - with explicit permissions
COPY --chown=scraper:scraper --chmod=644 . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import selenium; from selenium import webdriver; \
  options = webdriver.ChromeOptions(); \
  options.add_argument('--headless=new'); \
  options.add_argument('--no-sandbox'); \
  options.add_argument('--disable-dev-shm-usage'); \
  driver = webdriver.Chrome(options=options); \
  driver.get('about:blank'); \
  assert '' == driver.title; \
  driver.quit()" || exit 1

# Runtime command - using exec form with Xvfb
CMD ["sh", "-c", "Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} -ac +extension RANDR & export DISPLAY=:99 && python hi_candidate_screenshot_job.py"]
