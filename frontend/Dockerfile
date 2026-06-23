FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:alpine

RUN apk add --no-cache gettext

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY start-nginx.sh /usr/local/bin/start-nginx

RUN chmod +x /usr/local/bin/start-nginx

COPY --from=build /app/dist/frontend/browser/ /usr/share/nginx/html/

ENV API_UPSTREAM=http://fa-agent-api-qi

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health || exit 1

ENTRYPOINT ["/usr/local/bin/start-nginx"]