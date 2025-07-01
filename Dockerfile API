# Use a standard, stable Python runtime as a parent image.
FROM python:3.11-slim-bookworm

# Set -ex to exit immediately if a command exits with a non-zero status.
SHELL ["/bin/bash", "-c"]
RUN set -ex

# Set the timezone to prevent interactive prompts during deployment
ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies required for database drivers (libpq-dev for pg8000)
# and other common build tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    git \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory and create a non-root user for security best practices.
RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

# Copy the requirements file into the working directory.
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies specified in requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code into the working directory.
COPY --chown=appuser:appuser pull_and_link_cvs.py .

# Command to run the application when the container starts.
ENTRYPOINT ["python", "pull_and_link_cvs.py"]
