FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies
FROM base AS deps
COPY package.json ./
RUN npm install

# Development
FROM base AS development
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3001
CMD ["npm", "run", "dev"]

# Production
FROM base AS production
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
EXPOSE 3001
CMD ["npm", "run", "start"]