# Use a standard Python base image
FROM python:3.11-bookworm

# Set timezone
ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/timezone && echo $TZ > /etc/timezone

# Install system dependencies PLUS the virtual screen (xvfb)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip curl gnupg2 ca-certificates fonts-liberation libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 xdg-utils libu2f-udev libvulkan1 \
    xvfb && \
    rm -rf /var/lib/apt/lists/*

# Install Chrome for Testing v127
RUN CHROME_VERSION="127.0.6533.72" && \
    wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mkdir -p /opt/chrome && \
    mv chrome-linux64/* /opt/chrome/ && \
    rm -rf chrome-linux64.zip chrome-linux64

# Create a non-root user
RUN useradd --create-home appuser

# Install the matching ChromeDriver and set correct permissions
RUN CHROME_VERSION="127.0.6533.72" && \
    wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
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

# Copy application code
COPY --chown=appuser:appuser daily_CV_and_candidate_importer.py .

# ✅ FIX: Use xvfb-run to start the virtual screen and then run the Python script
# The --auto-servernum and --server-args ensure it runs cleanly in the container.
ENTRYPOINT ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "python", "daily_CV_and_candidate_importer.py"]
