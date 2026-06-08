# Official link registry

Last verified: 2026-06-08

This file keeps official links used by News_Crawling. Prefer these links over duplicated URLs in new docs.

## Project sources

- OpenAI News RSS
  - https://openai.com/news/rss.xml
  - Use for: OpenAI news source feed configured by the project.

## Groq

- Groq Docs
  - https://console.groq.com/docs
  - Use for: Groq API behavior and OpenAI-compatible integration notes.

- Groq API Reference
  - https://console.groq.com/docs/api-reference
  - Use for: endpoint and response details when summarizer behavior changes.

## Discord

- Discord Webhooks
  - https://docs.discord.com/developers/platform/webhooks
  - Use for: incoming webhook behavior and delivery semantics.

- Discord Webhook Resource
  - https://discord.com/developers/docs/resources/webhook
  - Use for: webhook resource fields, operations, and limits.

## Node.js

- Node.js TypeScript support
  - https://nodejs.org/dist/latest/docs/api/typescript.html
  - Use for: `node --experimental-transform-types` runtime behavior.

- Node.js SQLite
  - https://nodejs.org/api/sqlite.html
  - Use for: local SQLite state-store behavior.

## Playwright

- Playwright documentation
  - https://playwright.dev/docs/intro
  - Use for: browser automation dependency and source extraction behavior.

## Freshness policy

- Re-check links before changing external integration behavior.
- Update `Last verified` only after checking the links.
- If official docs change behavior, update `docs/REFERENCES.md` and the relevant source/service code comments or tests.
