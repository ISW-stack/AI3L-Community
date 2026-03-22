# Stage 0: Dev server (used by docker-compose.override.yml for local development)
FROM node:22-alpine AS dev

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# Source code is bind-mounted at runtime (./frontend:/app)
# node_modules is kept via anonymous volume to avoid being overwritten by the bind mount
EXPOSE 3210
CMD ["npm", "run", "dev"]

# Stage 1: Build
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid
USER nginx

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
