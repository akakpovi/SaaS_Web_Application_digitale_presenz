# Stage 1 : Build React
FROM node:20-alpine AS builder

WORKDIR /app

# Variables Vite : lues au build, avant npm run build.
ARG VITE_API_URL=/api/v1
ARG VITE_BASE_URL=https://localhost
ARG VITE_WP_API_URL=/cms
ARG PRERENDER_WP_API_URL=http://127.0.0.1:8081

ENV VITE_API_URL=$VITE_API_URL \
    VITE_BASE_URL=$VITE_BASE_URL \
    VITE_WP_API_URL=$VITE_WP_API_URL \
    PRERENDER_WP_API_URL=$PRERENDER_WP_API_URL

# Installer avec le lockfile pour un build reproductible.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copier le code source
COPY . .

# Build de production
RUN npm run build

# Stage 2 : Servir avec Nginx
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
