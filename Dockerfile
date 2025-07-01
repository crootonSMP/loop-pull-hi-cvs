# Use a specific Node.js version for your base image
FROM node:20-slim

# Set working directory inside the container
WORKDIR /usr/src/app

# Install Puppeteer and other Node.js dependencies
# Copy package.json and package-lock.json first to leverage Docker layer caching
COPY package.json ./
RUN npm install --omit=dev # --omit=dev skips devDependencies for smaller image

# Copy your application code
# Copies everything from your local project directory into the container's WORKDIR
COPY . .

# Command to run your Node.js script when the container starts
CMD ["node", "index.js"]
