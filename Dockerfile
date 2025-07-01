FROM node:20-slim

WORKDIR /usr/src/app
# Install Puppeteer and other Node.js dependencies
COPY package.json ./

RUN npm install

# ... (lines before your apt-get install block) ...

# Install missing shared libraries for Chrome and other common dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm-common \
    libgbm1 \
    libxshmfence1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libasound2 \
    fonts-liberation \
    fontconfig \
    xdg-utils \
    dbus-x11 \
    lsb-release \
    libgconf-2-4 \
    libssl-dev \
    zlib1g-dev \
    libffi-dev \
    libxkbcommon0 \ # <--- ADD THIS LINE
    && rm -rf /var/lib/apt/lists/*
# ... (rest of your Dockerfile) ...
COPY . .

# Run the script
CMD ["node", "index.js"]
