# Use a pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:latest

ENV TZ=Europe/London

# Switch to the default user provided by the Selenium image (usually 'seluser')
USER seluser
# The typical home directory for 'seluser' in Selenium images
WORKDIR /home/seluser

# Install Python dependencies from requirements.txt
# We'll create a virtual environment for your dependencies.
RUN python3 -m venv venv && \
    venv/bin/python -m pip install --upgrade pip --break-system-packages # <-- FIX APPLIED HERE: Use venv's pip

# Add the virtual environment's bin directory to the PATH
ENV PATH="/home/seluser/venv/bin:$PATH"

# Copy your requirements.txt file into the container
COPY --chown=seluser:seluser requirements.txt .

# Install Python dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages # This pip will now be the one from venv/bin

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
