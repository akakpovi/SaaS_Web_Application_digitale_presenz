# Stage 1 : Build React
FROM node:20-alpine AS builder

WORKDIR /app

# Copier package.json uniquement
COPY package.json ./

# Installer avec npm (pas pnpm - compatibilite Docker)
RUN npm install

# Copier le code source
COPY . .

# Build de production
RUN VITE_API_BASE_URL=/api/v1 npm run build

# Stage 2 : Servir avec Nginx
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
COPY --from=builder /app/dist/prerender /usr/share/nginx/html/prerender

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
