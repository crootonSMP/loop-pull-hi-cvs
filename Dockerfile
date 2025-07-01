# Use Selenium’s Chrome base image with built-in Chrome, Chromedriver, and Xvfb
FROM selenium/standalone-chrome:124.0

# Set timezone
ENV TZ=Europe/London

# Use root temporarily to install pip and packages
USER root

# Install pip
RUN apt-get update && apt-get install -y python3-pip

# Copy and install Python dependencies system-wide
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Switch back to non-root user
USER seluser
WORKDIR /home/seluser

# Copy Python script (as seluser)
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# Entrypoint to run the script inside the preconfigured display environment
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (system install) ---' >&2; \
  export DISPLAY=:99; \
  python3 hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
