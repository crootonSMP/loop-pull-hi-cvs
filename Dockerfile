# Use Selenium’s Chrome base image
FROM selenium/standalone-chrome:124.0

ENV TZ=Europe/London

# Switch to root to install pip
USER root

# Install pip
RUN apt-get update && apt-get install -y python3-pip

# Switch back to seluser (non-root)
USER seluser
WORKDIR /home/seluser

# Copy requirements and install
COPY --chown=seluser:seluser requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy your script
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# Run the script with Chrome and DISPLAY configured
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (no venv) ---' >&2; \
  export DISPLAY=:99; \
  python3 hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
