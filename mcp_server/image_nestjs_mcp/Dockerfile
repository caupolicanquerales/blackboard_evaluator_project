FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production

# Production dependencies only (no devDependencies)
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder /app/dist ./dist

# Run as non-root user provided by the node image
USER node

# Run compiled JS entrypoint communicating via stdio
ENTRYPOINT ["node", "dist/index.js"]