# Use a fuller Debian base image
FROM debian:bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London

# Install Python 3.11, pip, and essential build tools
# Also include all system packages for Chrome headless
# This RUN command is now correctly structured with backslashes and && operators.
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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

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

# --- TEMPORARY ENTRYPOINT FOR EXTREME EARLY DEBUGGING (Simplified to avoid parsing issues) ---
# This will run your Python script, then list/cat temporary files, then exit.
ENTRYPOINT ["/bin/bash", "-c", "echo '--- ENTRYPOINT START ---' >&2; echo '--- Verifying Python availability ---' >&2; which python >&2; which python3.11 >&2; python --version >&2; echo '--- Starting Xvfb ---' >&2; Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & XVFB_PID=$!; sleep 3; if ! kill -0 $XVFB_PID > /dev/null 2>&1; then echo '--- ERROR: Xvfb process '$XVFB_PID' died immediately! ---' >&2; cat /tmp/Xvfb_error_log.txt >&2 || true; exit 1; fi; echo '--- Xvfb started with PID '$XVFB_PID' ---' >&2; echo '--- Running Python script (full output redirected) ---' >&2; python hi_candidate_screenshot_job.py > /tmp/python_output.log 2>&1; SCRIPT_EXIT_CODE=$?; echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; cat /tmp/python_output.log >&2; echo '--- End Python script output ---' >&2; kill $XVFB_PID || true; echo '--- Xvfb process killed ---' >&2; echo '--- Listing files in current directory (/home/appuser/app) ---' >&2; ls -lh /home/appuser/app >&2; echo '--- Attempting to print contents of any PNG files (WARNING: binary output) ---' >&2; for f in /home/appuser/app/*.png; do if [ -f \"$f\" ]; then echo \"--- Contents of $f ---\" >&2; cat \"$f\" >&2; echo \"--- End contents of $f ---\" >&2; fi; done; echo '--- CHROME DEBUG LOG from Python run (if any) ---' >&2; if [ -f /tmp/chrome_debug_python.log ]; then cat /tmp/chrome_debug_python.log >&2; else echo 'No /tmp/chrome_debug_python.log found.' >&2; fi; echo '--- END CHROME DEBUG LOG ---' >&2; echo '--- Container exiting with final code: '$SCRIPT_EXIT_CODE' ---' >&2; exit $SCRIPT_EXIT_CODE; "]
