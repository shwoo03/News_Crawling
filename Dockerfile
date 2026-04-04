FROM node:24-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json README.md tsconfig.json ./
COPY src ./src

RUN mkdir -p /app/data
RUN npm ci --omit=dev
RUN npx playwright install --with-deps chromium

CMD ["node", "--experimental-transform-types", "src/index.ts"]
