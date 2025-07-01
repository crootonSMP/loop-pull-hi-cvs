# Use Selenium base image with Chrome
FROM selenium/standalone-chrome:latest

# Set timezone
ENV TZ=Europe/London

# Switch to root to install packages
USER root
WORKDIR /home/seluser

# Upgrade pip globally (no venv)
RUN pip install --upgrade pip

# Install Python dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your script
COPY hi_candidate_screenshot_job.py .

# Switch back to seluser
USER seluser

# Run your script
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python3 hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
