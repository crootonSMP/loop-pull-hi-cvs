FROM node:20-slim

WORKDIR /usr/src/app

# Install Puppeteer and other Node.js dependencies
COPY package.json ./
RUN npm install

# --- FIX: Install missing shared libraries for Chrome ---
# libgobject-2.0.so.0 is provided by libglib2.0-0 (already added from previous step)
# libnss3.so is provided by libnss3
# --- FIX: Install missing shared libraries for Chrome ---
# libgobject-2.0.so.0 is provided by libglib2.0-0
# libnss3.so is provided by libnss3
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \  # <--- Ensure this line (and previous package lines) ends with a backslash
    libnss3 \
    # Often, a more comprehensive list of common Chrome dependencies is recommended for minimal images:
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm-common \ # Replaces libdrm-dev for runtime
    libgbm1 \       # Replaces libgbm-dev for runtime
    libxshmfence1 \ # Replaces libxshmfence-dev for runtime
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libasound2 \
    # Font related (often important for rendering consistency)
    fonts-liberation \
    fontconfig \
    # Basic utilities often needed
    xdg-utils \
    # D-Bus (often noisy but sometimes needed by Chrome)
    dbus-x11 \
    # LSB (sometimes checked by Chrome startup scripts)
    lsb-release \
    # GConf (older, but sometimes still pulled in by transitive deps)
    libgconf-2-4 \
    # SSL and compression (critical for Python as well)
    libssl-dev \
    zlib1g-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*
# --- END FIX ---
# Copy your application code
COPY . .

# Run the script
CMD ["node", "index.js"]
