FROM selenium/standalone-chrome:123.0

# Switch to root to install additional packages
USER root

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev && \
    pip3 install --upgrade pip

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy script
COPY scrape_cv_links.py /app/scrape_cv_links.py

# Set working dir
WORKDIR /app

# Command to run your script
CMD ["python3", "scrape_cv_links.py"]
