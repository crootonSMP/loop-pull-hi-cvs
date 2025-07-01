# Use a slim Python base image
FROM python:3.11-slim-bookworm

# Environment setup
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London

# Install required packages (Chrome + system deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    ca-certificates \
    curl \
    unzip \
    wget \
    gnupg \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm-dev \
    libgbm-dev \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxshmfence-dev \
    libxkbcommon0 \
    xdg-utils \
    tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Google Chrome
RUN mkdir -p /etc/apt/keyrings && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install Chromedriver (version must match Chrome)
ENV CHROMEDRIVER_VERSION=125.0.6422.141
RUN mkdir -p /usr/bin/chromedriver && \
    wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O chromedriver.zip && \
    unzip chromedriver.zip -d /usr/bin/chromedriver && \
    rm chromedriver.zip && \
    ln -s /usr/bin/chromedriver/chromedriver-linux64/chromedriver /usr/bin/chromedriver/chromedriver && \
    chmod +x /usr/bin/chromedriver/chromedriver

ENV PATH="/usr/bin/chromedriver:$PATH"

# Create non-root user for security
RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

# Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy job script
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# Entrypoint
ENTRYPOINT ["python", "hi_candidate_screenshot_job.py"]
