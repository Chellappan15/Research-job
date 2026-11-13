# Build the dashboard, then serve it with Caddy (which also proxies /api to the backend).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Empty = same origin (/api via Caddy). Set only if the API lives on another domain.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
