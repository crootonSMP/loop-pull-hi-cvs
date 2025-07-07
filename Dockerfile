# Dockerfile for the Consolidated API to DB Importer Job
FROM python:3.11-slim-bookworm

# Set timezone
ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install only necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home appuser
WORKDIR /home/appuser/app
USER appuser

# Copy and install requirements
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser daily_candidate_importer.py .

# Run the script
ENTRYPOINT ["python", "daily_CV_and_candidate_importer.py"]
