FROM node:22-alpine

WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
COPY fixtures/ /workspace/fixtures/

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
