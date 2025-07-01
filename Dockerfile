# Use a pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:latest 

# Set timezone (if different from default in Selenium image)
ENV TZ=Europe/London

# Switch to root to perform system-level installations
USER root

# Install common utilities (as a last resort for very obscure missing dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# NO LONGER INSTALLING PYTHON3-PIP explicitly, it's typically present.
# We will use pip directly below.

# Switch back to the default non-root user for security
USER seluser
# The typical home directory for 'seluser' in Selenium images
WORKDIR /home/seluser

# --- FIX: INSTALL PYTHON DEPENDENCIES SYSTEM-WIDE (no venv) ---
# Copy requirements.txt to a location where 'seluser' can read it
COPY --chown=seluser:seluser requirements.txt .

# Install Python dependencies system-wide (as 'seluser' if pip allows, or use root temporarily)
# Use 'python3 -m pip' to invoke pip reliably
# --break-system-packages is still crucial for system-wide installs on these base images
RUN python3 -m pip install --no-cache-dir -r requirements.txt --break-system-packages
# --- END FIX ---

# Removed venv creation and activation (ENV PATH=...) as we're installing system-wide.
# Removed: RUN python3 -m venv venv ...
# Removed: ENV PATH="/home/seluser/venv/bin:$PATH"

# Copy your Python application script into the container
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# --- Simplified ENTRYPOINT remains the same ---
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
