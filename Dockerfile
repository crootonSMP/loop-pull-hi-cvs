# Use a pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:124.0

ENV TZ=Europe/London

# Switch to the default user provided by the Selenium image
USER seluser
WORKDIR /home/seluser

# Install Python dependencies directly (NO venv)
COPY --chown=seluser:seluser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your script
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# Run the script
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (no venv) ---' >&2; \
  export DISPLAY=:99; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
