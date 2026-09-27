# EstateMind web: CRA production build served by nginx.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Optional build-time default; the runtime API_BASE_URL (config.js) wins.
ARG REACT_APP_API_URL=
ENV REACT_APP_API_URL=$REACT_APP_API_URL
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/40-write-config-js.sh /docker-entrypoint.d/40-write-config-js.sh
RUN chmod +x /docker-entrypoint.d/40-write-config-js.sh
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
