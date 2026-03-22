# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build argument for API URL (set at build time)
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy NAS-specific nginx config (host network, port 5180, proxy to localhost:8010)
COPY nginx.nas.conf /etc/nginx/conf.d/default.conf

# Expose port 5180
EXPOSE 5180

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
