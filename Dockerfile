FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London

# Install system packages (keeping your latest additions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip wget gnupg ca-certificates fonts-liberation \
    libappindicator3-1 libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libgdk-pixbuf2.0-0 \
    libglib2.0-0 libnspr4 libnss3 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libxrender1 libxshmfence1 libxkbcommon0 xdg-utils \
    fontconfig \
    dbus-x11 \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and Chromedriver (version 125)
ENV CHROME_VERSION=125.0.6422.141

# Install Chrome
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mv chrome-linux64 /opt/chrome && \
    rm chrome-linux64.zip && \
    ln -s /opt/chrome/chrome /usr/bin/google-chrome

# Install Chromedriver
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf chromedriver-linux64.zip chromedriver-linux64

# Add non-root user
RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

# Install Python requirements
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script
COPY --chown=appuser:appuser hi_candidate_screenshot_job.py .

# --- TEMPORARY ENTRYPOINT FOR DEEP DEBUGGING ---
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Attempting Chrome manual launch ---'; \
  /opt/chrome/chrome/chrome --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --dump-dom 'about:blank' > /tmp/chrome_manual_output.log 2>&1; \
  RET_CODE=$?; \
  echo '--- Chrome manual launch exited with code: '$RET_CODE' ---'; \
  cat /tmp/chrome_manual_output.log; \
  echo '--- End Chrome manual launch output ---'; \
  \
  # Now try to run the main script (it will likely fail the same way but good to keep the flow) \
  echo '--- Attempting Python script launch ---'; \
  python hi_candidate_screenshot_job.py 2>&1 | tee /dev/stderr; \
  if [ -f /tmp/chrome_debug.log ]; then \
    echo '--- CHROME DEBUG LOG from Python run ---'; \
    cat /tmp/chrome_debug.log; \
    echo '--- END CHROME DEBUG LOG ---'; \
  fi \
"]
# --- END TEMPORARY ENTRYPOINT ---
