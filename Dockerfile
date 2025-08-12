# Use a standard Python base image
FROM python:3.11-bookworm

# ARG for version makes it easy to update and override at build time
ARG CHROME_VERSION="128.0.6613.119"

# Set timezone and PATH. Grouping ENV variables is good practice.
ENV TZ=Europe/London
ENV PATH="/opt/chrome:${PATH}"

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Set timezone non-interactively
    tzdata \
    # Browser dependencies
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libglib2.0-0 \
    libxkbcommon0 \
    xvfb \
    xauth \
    # Process manager
    tini \
    # Utilities
    wget \
    unzip \
    curl \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome for Testing and the matching ChromeDriver in a single layer
RUN wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip chrome-linux64.zip \
    && unzip chromedriver-linux64.zip \
    && mkdir -p /opt/chrome \
    && mv chrome-linux64/* /opt/chrome/ \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf chrome-linux64.zip chromedriver-linux64.zip chrome-linux64 chromedriver-linux64

# Create a non-root user and its home directory
RUN useradd --create-home --shell /bin/bash appuser

# Create and set permissions for a temp directory the user will own
# The user does NOT need to own the chrome or chromedriver binaries
RUN mkdir -p /tmp && chown -R appuser:appuser /tmp

# Switch to the non-root user
USER appuser
WORKDIR /home/appuser/app

# Install Python dependencies, leveraging layer caching
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and entrypoint script
COPY --chown=appuser:appuser daily_CV_and_candidate_importer.py .
COPY --chown=appuser:appuser entrypoint.sh .
RUN chmod +x entrypoint.sh

# Use tini as the container's init process
ENTRYPOINT ["/usr/bin/tini", "--"]

# Set the default command to run
CMD ["./entrypoint.sh"]
