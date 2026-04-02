FROM node:24-bookworm-slim

WORKDIR /app

COPY package.json README.md tsconfig.json ./
COPY src ./src

RUN mkdir -p /app/data

CMD ["node", "--experimental-transform-types", "src/index.ts"]
