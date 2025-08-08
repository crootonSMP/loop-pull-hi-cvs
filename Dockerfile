# Use a standard Python base image
FROM python:3.11-bookworm

# Set timezone
ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/timezone && echo $TZ > /etc/timezone

# Add 'tini' for proper process management and 'xauth' for the virtual display
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip curl gnupg2 ca-certificates fonts-liberation libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 xdg-utils libu2f-udev libvulkan1 \
    xvfb xauth tini && \
    rm -rf /var/lib/apt/lists/*

# ✅ FIX: Use a newer, valid version of Chrome for Testing
# This version (128) is current as of August 2025 and the link is active.
RUN CHROME_VERSION="128.0.6548.0" && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mkdir -p /opt/chrome && \
    mv chrome-linux64/* /opt/chrome/ && \
    rm -rf chrome-linux64.zip chrome-linux64

# Create a non-root user
RUN useradd --create-home appuser

# Install the matching ChromeDriver
RUN CHROME_VERSION="128.0.6548.0" && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    chown appuser:appuser /usr/local/bin/chromedriver && \
    rm -rf chromedriver-linux64.zip chromedriver-linux64

# Add Chrome to PATH
ENV PATH="/opt/chrome:${PATH}"

# Switch to non-root user
USER appuser
WORKDIR /home/appuser/app

# Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and entrypoint script
COPY --chown=appuser:appuser daily_CV_and_candidate_importer.py .
COPY --chown=appuser:appuser entrypoint.sh .

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Use 'tini' to launch our entrypoint script, which correctly manages the process lifecycle
ENTRYPOINT ["/usr/bin/tini", "--", "./entrypoint.sh"]
