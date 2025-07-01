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
# Check the Selenium Docker image releases page on GitHub for exact Python versions:
# https://github.com/SeleniumHQ/docker-selenium/releases
# As of current information (from search results), it uses Ubuntu 24.04 LTS which ships with Python 3.12 by default.
# The `python3 -m venv venv` should work.
RUN python3 -m venv venv && \
    /usr/bin/python3 -m pip install --upgrade pip

# Add the virtual environment's bin directory to the PATH
ENV PATH="/home/seluser/venv/bin:$PATH"

# Copy your requirements.txt file into the container
COPY --chown=seluser:seluser requirements.txt .

# Install Python dependencies into the virtual environment
# The --break-system-packages is crucial for newer Debian/Ubuntu base images
# which prevent direct system-wide pip installs.
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

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
