# Use a specific, stable pre-built Selenium image with Chrome
# 4.18.1 is often cited as a stable version, or choose another specific tag from Docker Hub
FROM selenium/standalone-chrome:4.18.1 

# Set timezone (if different from default in Selenium image)
ENV TZ=Europe/London

# Switch to the default user provided by the Selenium image (usually 'seluser')
USER seluser
# The typical home directory for 'seluser' in Selenium images
WORKDIR /home/seluser

# Install common utilities (as a last resort for very obscure missing dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
# We'll create a virtual environment for your dependencies.
RUN python3 -m venv venv && \
    /usr/bin/python3 -m pip install --upgrade pip --break-system-packages

# Add the virtual environment's bin directory to the PATH
ENV PATH="/home/seluser/venv/bin:$PATH"

# Copy your requirements.txt file into the container
COPY --chown=seluser:seluser requirements.txt .

# Install Python dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

# Copy your Python application script into the container
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# --- Simplified ENTRYPOINT ---
# The Selenium image handles Xvfb/display and Chrome/Chromedriver setup internally.
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
