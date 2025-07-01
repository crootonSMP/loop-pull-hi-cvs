# Use Selenium base image with Chrome and Python preinstalled
FROM selenium/standalone-chrome:latest

# Set timezone
ENV TZ=Europe/London

# Switch to default non-root user
USER seluser
WORKDIR /home/seluser

# Create and activate a virtual environment, upgrade pip
RUN python3 -m venv venv && \
    /usr/bin/python3 -m pip install --upgrade pip --break-system-packages

# Add virtualenv to PATH
ENV PATH="/home/seluser/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY --chown=seluser:seluser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

# Copy your Python script
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# Fix ENTRYPOINT typo and launch Python
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
