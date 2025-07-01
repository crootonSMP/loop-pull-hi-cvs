FROM node:20-slim # Or a specific Node.js version you prefer

WORKDIR /usr/src/app

# Install Puppeteer and other Node.js dependencies
COPY package.json ./
RUN npm install

# Copy your application code
COPY . .

# Run the script
CMD ["node", "index.js"]
