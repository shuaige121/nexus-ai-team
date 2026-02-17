# ══════════════════════════════════════════════════════════════════════════════
# NEXUS Dashboard — Multi-stage Dockerfile
# ══════════════════════════════════════════════════════════════════════════════
#
# Stages:
#   1. base        — Node.js base
#   2. builder     — Build React app
#   3. production  — Nginx serving static files
#   4. development — Vite dev server with HMR
#

# ── Stage 1: Base ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies for building
RUN apk add --no-cache libc6-compat

# ── Stage 2: Builder ──────────────────────────────────────────────────────────
FROM base AS builder

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# ── Stage 3: Production (Nginx) ───────────────────────────────────────────────
FROM nginx:alpine AS production

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

# ── Stage 4: Development ──────────────────────────────────────────────────────
FROM base AS development

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source code (will be overridden by volume mount in dev)
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
