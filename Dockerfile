# Stage 1: Builder - Modernized with security improvements
FROM python:3.10-slim as builder

# Set build arguments with defaults
ARG TZ=Europe/London
ARG DEBIAN_FRONTEND=noninteractive
ARG CHROME_VERSION="116.0.5845.96-1"  # Pinned stable version

# System configuration - consolidated ENV
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=${TZ} \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

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
    libgbm-dev \
    libasound2 \
    libxss1 \
    libcups2 \
    libdbus-glib-1-2 \
    libxtst6 \
    libxrender1 \
    libxi6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome - using pinned version
RUN wget -q -O /tmp/google-chrome.deb \
    "https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}_amd64.deb" \
    && apt-get install -y --no-install-recommends /tmp/google-chrome.deb \
    && rm -f /tmp/google-chrome.deb

# Install ChromeDriver - using chrome-for-testing endpoint
RUN CHROME_MAJOR=$(google-chrome --version | cut -d ' ' -f3 | cut -d '.' -f1) \
    && CHROMEDRIVER_VERSION=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_$CHROME_MAJOR") \
    && wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

# Stage 2: Runtime - Security hardened
FROM python:3.10-slim

# Copy only the minimal required files from builder
COPY --from=builder /usr/bin/google-chrome /usr/bin/
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/
COPY --from=builder /usr/lib/chromium-browser/ /usr/lib/chromium-browser/
COPY --from=builder /usr/lib/x86_64-linux-gnu/ /usr/lib/x86_64-linux-gnu/

# Copy only required library dependencies
COPY --from=builder /usr/share/fonts /usr/share/fonts
COPY --from=builder /etc/fonts /etc/fonts

# Environment variables - security focused
ENV CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/scraper/.local/bin:$PATH"

# Create secure non-root user environment
RUN groupadd -r scraper && \
    useradd -r -g scraper -d /app -s /sbin/nologin scraper && \
    mkdir -p /app && \
    chown -R scraper:scraper /app

WORKDIR /app
USER scraper

# Install Python dependencies - optimized for caching
COPY --chown=scraper:scraper requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application code - with explicit permissions
COPY --chown=scraper:scraper --chmod=644 . .

# Runtime command - using exec form
CMD ["python", "hi_candidate_screenshot_job.py"]
