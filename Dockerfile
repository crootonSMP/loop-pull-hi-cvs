# Use a pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:latest 

# Set timezone (if different from default in Selenium image)
ENV TZ=Europe/London

# Switch to the default user provided by the Selenium image (usually 'seluser')
# The selenium/standalone-chrome image typically runs as 'seluser' by default.
USER seluser
# The typical home directory for 'seluser' in Selenium images
WORKDIR /home/seluser 

# Install Python dependencies from requirements.txt
# The selenium/standalone-chrome image usually comes with Python 3.x installed.
# We'll create a virtual environment for your dependencies.
# Use 'python3' as the executable name, as that's typical in these images.
RUN python3 -m venv venv && \
    /usr/bin/python3 -m pip install --upgrade pip
ENV PATH="/home/seluser/venv/bin:$PATH"
COPY --chown=seluser:seluser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python application script into the container
COPY --chown=seluser:seluser hi_candidate_screenshot_job.py .

# --- Simplified ENTRYPOINT for pre-built image ---
# The Selenium image handles Xvfb/display and Chrome/Chromedriver setup internally.
# We just run your Python script.
ENTRYPOINT ["/bin/bash", "-c", "\
  echo '--- Running Python script (from Selenium base image) ---' >&2; \
  python hi_candidate_screenshot_job.py 2>&1; \
  SCRIPT_EXIT_CODE=$?; \
  \
  echo '--- Python script finished with exit code: '$SCRIPT_EXIT_CODE' ---' >&2; \
  exit $SCRIPT_EXIT_CODE; \
"]
