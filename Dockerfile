FROM node:24-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json README.md tsconfig.json ./
COPY src ./src

RUN mkdir -p /app/data
RUN npm ci --omit=dev
RUN npx playwright install --with-deps chromium

ENV DASHBOARD_HOST=0.0.0.0 \
    DASHBOARD_PORT=3000

EXPOSE 3000

CMD ["node", "--experimental-transform-types", "src/index.ts"]
