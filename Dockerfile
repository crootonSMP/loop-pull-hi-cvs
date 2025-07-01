# Use a specific Node.js version for your base image
FROM node:20-slim

WORKDIR /usr/src/app

# Install Puppeteer and other Node.js dependencies
COPY package.json ./
RUN npm install

# --- FIX: Install missing shared library for Chrome ---
# libgobject-2.0.so.0 is provided by libglib2.0-0
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    # You might also need other common Chrome dependencies if this doesn't fully resolve it.
    # Often, a list like the one from our earlier Python setup is good:
    # libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm-dev libgbm-dev libxshmfence-dev libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxrender1
    && rm -rf /var/lib/apt/lists/*
# --- END FIX ---

# Copy your application code
COPY . .

# Run the script
CMD ["node", "index.js"]
