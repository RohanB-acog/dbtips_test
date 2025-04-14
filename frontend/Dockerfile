# Step 1: Build the React app
FROM node:22-alpine as build

# Install git in alpine (required for git-based dependencies)
RUN apk add --no-cache git

# Set the working directory
WORKDIR /app

# Copy .tgz and package files
COPY chatbot-component-1.0.0.tgz ./
COPY package*.json ./

# Install latest npm
RUN npm install -g npm@11.2.0

# Install dependencies
RUN npm install

# Copy the rest of the app
COPY . .

# Build with env variables
ARG VITE_API_URI
ARG VITE_TARGET_DOSSIER_URI
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN VITE_API_URI=${VITE_API_URI} VITE_TARGET_DOSSIER_URI=${VITE_TARGET_DOSSIER_URI} npm run build

# Step 2: Serve with Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]