# Dockerfile for the Consolidated API to DB Importer Job with Selenium
FROM python:3.11-slim-bookworm

# Install system dependencies for headless Chrome
# This section is critical for Selenium to work in a Docker environment
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    ca-certificates \
    curl \
    unzip \
    xvfb \
    libglib2.0-0 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm-dev \
    libatk-bridge2.0-0 \
    libcups2 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libfontconfig1 \
    libasound2 \
    --fix-missing \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium Browser (headless version)
# Using `chromium-browser` and `chromium-driver` from Debian repos
RUN apt-get update && apt-get install -y --no-install-recommends chromium-browser chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Add chromium-driver to PATH
ENV PATH="/usr/lib/chromium-browser/:${PATH}"

ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser multi_candidate_screenshot.py .

# Changed ENTRYPOINT to the new script name
ENTRYPOINT ["python", "multi_candidate_screenshot.py"]
