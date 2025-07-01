# Use a pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:latest 

# Set timezone (if different from default in Selenium image)
ENV TZ=Europe/London

# Switch to root to perform system-level installations
# This is necessary as apt-get requires root privileges.
USER root

# Install common utilities (as a last resort for very obscure missing dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# The selenium/standalone-chrome image typically has Python 3 with pip pre-installed.
# Removed: RUN apt-get install -y python3-pip && rm -rf /var/lib/apt/lists/*

# Switch back to the default non-root user for security
USER seluser
# The typical home directory for 'seluser' in Selenium images
WORKDIR /home/seluser

# Install Python dependencies into a virtual environment
# Create virtual environment and upgrade pip within it, explicitly breaking system packages
RUN python3 -m venv venv && \
    venv/bin/python3 -m pip install --upgrade pip --break-system-packages

# Add the virtual environment's bin directory to the PATH
ENV PATH="/home/seluser/venv/bin:$PATH"

# Copy your requirements.txt file into the container
COPY --chown=seluser:seluser requirements.txt .

# Install Python dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

# Copy your Python application script into the container
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# --- Simplified ENTRYPOINT for pre-built image ---
# The Selenium image handles Xvfb/display and Chrome/Chromedriver setup internally.
# This ENTRYPOINT simply runs your Python script.
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
