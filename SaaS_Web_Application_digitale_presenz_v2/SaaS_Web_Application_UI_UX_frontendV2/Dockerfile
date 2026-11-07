# Stage 1 : Build Frontend V2
FROM node:20-alpine AS builder

WORKDIR /app

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Build production
# Pass the public origin at build time so canonical URLs, sitemap and
# robots.txt are absolute (docker compose build --build-arg ...).
ARG VITE_BASE_URL=""
ARG VITE_WP_API_URL=""
# Build-only CMS URL (e.g. the loopback-published WordPress): it is used by
# prerender.mjs but never exposed to the browser bundle.
ARG PRERENDER_WP_API_URL=""
ENV VITE_BASE_URL=$VITE_BASE_URL \
    VITE_WP_API_URL=$VITE_WP_API_URL \
    PRERENDER_WP_API_URL=$PRERENDER_WP_API_URL
# Les variables sont répétées sur la commande : un cache Docker peut sinon
# réutiliser une couche compilée sans l'URL du CMS (blog en erreur).
RUN VITE_API_BASE_URL=/api/v1 \
    VITE_BASE_URL="$VITE_BASE_URL" \
    VITE_WP_API_URL="$VITE_WP_API_URL" \
    PRERENDER_WP_API_URL="$PRERENDER_WP_API_URL" \
    pnpm run build

# Stage 2 : Serve with Nginx
FROM nginx:1.27-alpine

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Redirect map generated from src/seo/publicPaths.ts during the build above.
# It must exist before nginx starts: `include` of a missing file is fatal.
COPY --from=builder /app/nginx.locale-map.conf /etc/nginx/conf.d/presence-locale-map.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]