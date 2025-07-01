
# Use a fuller Debian base image
FROM debian:bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London

# Install Python 3.11, pip, and essential build tools
# Also include all system packages for Chrome headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    python3.11-venv \
    build-essential \
    curl \
    unzip \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
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
    libxshmfence1 \
    libxkbcommon0 \
    xdg-utils \
    fontconfig \
    dbus-x11 \
    lsb-release \
    libgconf-2-4 \
    xvfb \
    libssl-dev \
    zlib1g-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set locale environment variables for Python
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set python3.11 as default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Pin Chrome and Chromedriver to a specific version for stability.
ENV CHROME_VERSION=125.0.6422.141

# Install Chrome binary from Chrome for Testing
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mv chrome-linux64 /opt/chrome && \
    rm chrome-linux64.zip && \
    ln -s /opt/chrome/chrome /usr/bin/google-chrome

# Install Chromedriver binary from Chrome for Testing
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf chromedriver-linux64.zip chromedriver-linux64

# Create the .X11-unix directory and set permissions BEFORE switching to non-root user
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    chown root:root /tmp/.X11-unix

# Create a non-root user for improved security
RUN useradd --create-home appuser

# Switch to the non-root user before performing operations as that user
USER appuser
# Set WORKDIR after switching user if it's user's home
WORKDIR /home/appuser/app

# Install Python dependencies from requirements.txt
COPY --chown=appuser:appuser requirements.txt .

# Create a virtual environment
RUN python3.11 -m venv venv

# Update PATH accordingly
ENV PATH="/home/appuser/app/venv/bin:$PATH"

# Install dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python application script into the container (duplicate removed)
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# Use a pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:latest # Using 'latest' for convenience, consider pinning a specific version for production

# Set timezone (if different from default in Selenium image)
ENV TZ=Europe/London

# Switch to the default user provided by the Selenium image (usually 'seluser')
# Check the documentation for selenium/standalone-chrome for its default user.
# It's often 'seluser' or similar. Assuming 'seluser' for now.
USER seluser
WORKDIR /home/seluser # The typical home directory for 'seluser' in Selenium images

# Install Python 3.11 and pip (these are usually included, but verify/add if not)
# Selenium images usually come with Python, but check its specific version.
# If Python 3.11 is not already present or you need a specific version, you may need to uncomment and adjust the following line
# RUN apt-get update && apt-get install -y python3.11 python3-pip python3.11-venv && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
# Create a virtual environment for isolation, as 'seluser'
# Use 'python3' as the executable name, as that's typical in these images
RUN python3 -m venv venv && \
    /usr/bin/python3 -m pip install --upgrade pip
ENV PATH="/home/seluser/venv/bin:$PATH"
COPY --chown=seluser:seluser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python application script into the container
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# --- Simplified ENTRYPOINT for pre-built image ---
# The Selenium image handles Xvfb/display and Chrome/Chromedriver setup internally.
# We just run your Python script.
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
