# Dockerfile for the Consolidated API to DB Importer Job
FROM python:3.11-slim-bookworm

# Install necessary system packages for Chrome and Chromedriver
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    ca-certificates \
    curl \
    # Dependencies for Chrome
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
    # Install Google Chrome
    wget \
    gnupg \
    --break-system-packages && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for timezone
ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Chromedriver manually, compatible with google-chrome-stable
# You might need to adjust this version based on the Chrome version installed.
# For stable-chrome, the latest chromedriver from storage.googleapis.com/chrome-for-testing-public/
# is usually compatible. Let's pick a specific stable version (e.g., 125.0.6422.141).
ENV CHROMEDRIVER_VERSION 125.0.6422.141
RUN mkdir -p /usr/bin/chromedriver && \
    wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O chromedriver.zip && \
    unzip chromedriver.zip -d /usr/bin/chromedriver && \
    rm chromedriver.zip && \
    ln -s /usr/bin/chromedriver/chromedriver-linux64/chromedriver /usr/bin/chromedriver/chromedriver && \
    chmod +x /usr/bin/chromedriver/chromedriver

ENV PATH="/usr/bin/chromedriver:$PATH"

# Create a non-root user
RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

# Copy requirements.txt and install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python script
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# Entrypoint for the job
ENTRYPOINT ["python", "hi_candidate_screenshot_job.py"]
