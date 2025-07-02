# Stage 1: Builder - Modernized with security improvements
FROM python:3.10-slim AS builder

# Set build arguments with defaults
ARG TZ=Europe/London
ARG DEBIAN_FRONTEND=noninteractive

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

# Install Chrome using Chrome for Testing
RUN CHROME_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chrome-linux64.zip" \
    && unzip chrome-linux64.zip -d /opt \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && rm chrome-linux64.zip

# Verify Chrome installation
RUN google-chrome --version

# Install matching Chromedriver
RUN CHROME_MAJOR=$(google-chrome --version | awk '{print $3}' | awk -F '.' '{print $1}') \
    && CHROMEDRIVER_VERSION=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_$CHROME_MAJOR") \
    && wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

# Stage 2: Runtime - Security hardened
FROM python:3.10-slim

# Copy only the minimal required files from builder
COPY --from=builder /usr/bin/google-chrome /usr/bin/
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/
COPY --from=builder /opt/chrome-linux64 /opt/chrome-linux64
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
