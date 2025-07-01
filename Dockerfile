# Use a fuller Debian base image
FROM debian:bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London

# ... (lines before RUN apt-get update) ...

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
    # --- ADD THESE CORE LIBRARIES ---
    libssl-dev \
    zlib1g-dev \
    libffi-dev \
    # --- END ADDITION ---
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# --- ADD THESE ENVIRONMENT VARIABLES FOR LOCALE ---
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
# --- END ADDITION ---

# ... (rest of your Dockerfile, including the ENTRYPOINT from last time) ...

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

# Create a non-root user for improved security (This section is unique and correct)
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

# Copy your Python application script into the container
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# Copy your Python application script into the container
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# ... (rest of your Dockerfile remains identical) ...

# --- FINAL ATTEMPT ENTRYPOINT FOR STABLE XVFB AND PYTHON ---
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- ENTRYPOINT START ---' >&2; \
  \
  # Start Xvfb in the background, redirect its output to a log file \
  echo '--- Starting Xvfb and capturing its output to /tmp/Xvfb.log ---' >&2; \
  Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /tmp/Xvfb.log 2>&1 & \
  XVFB_PID=$!; \
  \
  # Give Xvfb time to initialize and check if it's running \
  ATTEMPTS=0; \
  while [ $ATTEMPTS -lt 10 ]; do \
    if kill -0 $XVFB_PID > /dev/null 2>&1; then \
      echo '--- Xvfb started successfully with PID '$XVFB_PID' ---' >&2; \
      break; \
    else \
      echo '--- Waiting for Xvfb to start... (attempt '$ATTEMPTS') ---' >&2; \
      sleep 1; \
      ATTEMPTS=$((ATTEMPTS+1)); \
    fi; \
  done; \
  \
  # If Xvfb is still not running after attempts, exit with error \
  if ! kill -0 $XVFB_PID > /dev/null 2>&1; then \
    echo '--- ERROR: Xvfb did not start! Check /tmp/Xvfb.log below. ---' >&2; \
    cat /tmp/Xvfb.log >&2; \
    exit 1; \
  fi; \
  \
  # Run the Python script \
  echo '--- Running Python script ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  \
  # Clean up Xvfb process \
  kill $XVFB_PID || true; \
  echo '--- Xvfb process killed ---' >&2; \
  \
  # Display final logs (adjust based on python script's output) \
  echo '--- Container exiting with code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
