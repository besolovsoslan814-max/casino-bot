FROM node:18-alpine

WORKDIR /app

# Copy bot package files
COPY bot/package*.json ./bot/

# Install bot dependencies
RUN cd bot && npm install --production

# Copy bot files
COPY bot/ ./bot/

# Set working directory to bot
WORKDIR /app/bot

EXPOSE 3000

CMD ["node", "server.js"]
