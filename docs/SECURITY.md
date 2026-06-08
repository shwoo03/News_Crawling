# Security

## Secrets

Never commit real values for:

- `GROQ_API_KEY`
- `DISCORD_WEBHOOK_URL`
- `DISCORD_WEBHOOK_ID`
- `DISCORD_WEBHOOK_TOKEN`
- local `.env` files

Documentation may mention secret names and setup paths, but not secret values.
Use `.env.example` for placeholder names only.

## External services

This project calls external services:

- news source pages and feeds
- Groq API for summarization
- Discord Webhook for delivery

Treat all external responses as untrusted. Summaries must be based only on the article body gathered by the project. Do not add outside facts when summarizing.

## Local state

- The SQLite database path is controlled by `SQLITE_PATH` and defaults to `./data/news-crawling.sqlite`.
- Do not commit local runtime database files.
- Logs may include URLs and article titles. Do not log secrets or webhook tokens.

## Permissions

- Prefer read-only inspection before modifying source, runtime state, hooks, skills, MCP config, plugins, or CI.
- Ask before destructive operations, dependency changes, deployments, pushing, or modifying secret-handling behavior.
- Do not send live Discord webhooks unless the user explicitly asks for a live delivery check.

## Agent and tool surfaces

This repository already contains optional operating surfaces such as `runtime/`, `hooks/`, `mcp/`, `skills/`, `.claude/`, `.codex/`, and `.agents/`.

Do not add, remove, activate, or repackage these surfaces unless the user explicitly asks in the current turn. When changing them, record owner, rollback path, validation, and security boundary.

## Notion and documentation

Do not paste secrets, raw private payloads, Discord webhook URLs, Groq API keys, local database contents, or private logs into Notion or project docs. Use synthetic examples when examples are needed.
