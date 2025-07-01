# Use a slim Python base image for smaller size
FROM python:3.11-slim-bookworm

# Set environment variables for non-interactive installs and timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London

# Install essential system packages for Chrome headless
# This list includes dependencies identified through debugging.
# `apt-get clean` reduces image size by clearing package caches.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip wget gnupg ca-certificates fonts-liberation \
    libappindicator3-1 libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libgdk-pixbuf2.0-0 \
    libglib2.0-0 libnspr4 libnss3 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libxrender1 libxshmfence1 libxkbcommon0 xdg-utils \
    fontconfig \
    dbus-x11 \
    lsb-release \
    libgconf-2-4 \
    xvfb \
    && rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Pin Chrome and Chromedriver to a specific version for stability.
# This ensures perfect compatibility between the browser and its driver.
ENV CHROME_VERSION=125.0.6422.141

# Install Chrome binary from Chrome for Testing
# Unzips, moves the 'chrome-linux64' directory, renames it to 'chrome' inside /opt,
# then creates a symlink to make it accessible via a standard path.
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mv chrome-linux64 /opt/chrome && \
    rm chrome-linux64.zip && \
    ln -s /opt/chrome/chrome /usr/bin/google-chrome

# Install Chromedriver binary from Chrome for Testing
# Unzips, moves the 'chromedriver' executable directly to /usr/bin/,
# sets execute permissions, and cleans up temporary files/directories.
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf chromedriver-linux64.zip chromedriver-linux64

# Create a non-root user for improved security
RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

# Install Python dependencies from requirements.txt
# `--no-cache-dir` reduces the final image size.
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python application script into the container
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# --- TEMPORARY ENTRYPOINT FOR FILE INSPECTION AFTER SCRIPT RUN ---
# This will run your Python script, then list/cat temporary files, then exit.
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1 | tee /dev/stderr; \
  SCRIPT_EXIT_CODE=$?; \
  \
  echo '--- Listing files in current directory (/home/appuser/app) ---' >&2; \
  ls -lh /home/appuser/app >&2; \
  \
  echo '--- Attempting to print contents of any PNG files (WARNING: binary output) ---' >&2; \
  for f in /home/appuser/app/*.png; do \
    if [ -f \"$f\" ]; then \
      echo \"--- Contents of $f ---\" >&2; \
      cat \"$f\" >&2; \
      echo \"--- End contents of $f ---\" >&2; \
    fi \
  done; \
  \
  echo '--- CHROME DEBUG LOG from Python run (if any) ---' >&2; \
  if [ -f /tmp/chrome_debug_python.log ]; then \
    cat /tmp/chrome_debug_python.log >&2; \
  else \
    echo 'No /tmp/chrome_debug_python.log found.' >&2; \
  fi; \
  echo '--- END CHROME DEBUG LOG ---' >&2; \
  \
  echo '--- Container exiting with script code ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
