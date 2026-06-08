# References

Use this file to record project-specific references and adoption decisions.

## Adoption modes

- `reference-only`: read for background only.
- `concept-only`: use the idea, not code or API.
- `direct-dependency`: install and use as a package.
- `adapter`: wrap the library/SDK behind a small interface.
- `fork`: fork and maintain changes.
- `vendored-source`: copy source into this repo.
- `rejected`: considered but not used.

## Current decisions

### Groq OpenAI-compatible API

- URL: https://console.groq.com/docs
- Date checked: 2026-06-08
- Search terms checked: `Groq OpenAI compatible API docs official`
- License: service/API documentation, not vendored source
- Version / commit: not applicable
- Adoption mode: `adapter`
- Why relevant: `src/services/summarizer.ts` calls Groq's OpenAI-compatible chat completions endpoint for Korean article summaries.
- Decision: keep the small local `GroqSummarizer` adapter instead of adding a larger agent runtime.
- Integration plan: use environment variables for model and fallback list; keep retry/fallback behavior local and testable.
- Maintenance risk: API behavior, model names, rate limits, and response format may change.
- Security notes: `GROQ_API_KEY` is secret. Never log or document the value.
- Rejected alternatives: no broader SDK adoption recorded in this pass.
- Recheck when: Groq endpoint, model list, rate-limit behavior, or summary response format changes.

### Discord Webhook delivery

- URL: https://docs.discord.com/developers/platform/webhooks
- Date checked: 2026-06-08
- Search terms checked: `Discord webhook developer docs official`
- License: service/API documentation, not vendored source
- Version / commit: not applicable
- Adoption mode: `adapter`
- Why relevant: `src/services/discord.ts` posts summary embeds to a configured Discord webhook.
- Decision: keep direct webhook POST logic through `DiscordNotifier`.
- Integration plan: accept either `DISCORD_WEBHOOK_URL` or ID/token parts from environment variables.
- Maintenance risk: payload limits or webhook API behavior may change.
- Security notes: webhook URL and token are secrets. Mask or omit them in logs and docs.
- Rejected alternatives: no Discord bot framework adoption recorded in this pass.
- Recheck when: Discord webhook limits, embed fields, or auth model changes.

### Node native TypeScript execution

- URL: https://nodejs.org/dist/latest/docs/api/typescript.html
- Date checked: 2026-06-08
- Search terms checked: `Node.js type stripping TypeScript official docs`
- License: official documentation, not vendored source
- Version / commit: current runtime dependent
- Adoption mode: `direct-dependency`
- Why relevant: `package.json` runs `.ts` files with `node --experimental-transform-types`.
- Decision: preserve the current Node execution path until the project intentionally adds a build step.
- Integration plan: keep package scripts as the source of truth for start/top/test commands.
- Maintenance risk: experimental TypeScript execution behavior can change between Node versions.
- Security notes: not a secret-bearing surface.
- Rejected alternatives: no `tsx`, `ts-node`, or compile-to-JS migration recorded in this pass.
- Recheck when: Node version changes, tests fail due to TypeScript runtime behavior, or deployment needs stable compiled output.

### Node SQLite state store

- URL: https://nodejs.org/api/sqlite.html
- Date checked: 2026-06-08
- Search terms checked: `Node.js SQLite DatabaseSync official docs`
- License: official documentation, not vendored source
- Version / commit: current runtime dependent
- Adoption mode: `direct-dependency`
- Why relevant: `src/storage/sqlite.ts` stores seen article URLs to avoid duplicate delivery.
- Decision: keep SQLite as the local state store for this single-worker app.
- Integration plan: keep `SQLITE_PATH` configurable and default local data under `./data/`.
- Maintenance risk: local DB schema/state corruption or Node SQLite API changes.
- Security notes: do not commit local runtime databases.
- Rejected alternatives: no external database adoption recorded in this pass.
- Recheck when: multi-instance deployment, remote hosting, or concurrent writers become requirements.

### Playwright

- URL: https://playwright.dev/docs/intro
- Date checked: 2026-06-08
- Search terms checked: `Playwright official docs`
- License: package/license from dependency, not vendored source
- Version / commit: package dependency `^1.51.0`
- Adoption mode: `direct-dependency`
- Why relevant: source adapters can use browser automation for article/list extraction where plain HTTP is insufficient.
- Decision: preserve Playwright dependency and source-adapter tests.
- Integration plan: keep source adapters isolated under `src/sources/` and verify with fixture-based tests.
- Maintenance risk: source site layout changes and browser/runtime dependency changes.
- Security notes: do not automate authenticated private pages or store private page content.
- Rejected alternatives: no generic scraping framework adoption recorded in this pass.
- Recheck when: source pages change, Playwright install/runtime fails, or official feeds can replace browser extraction.

### Official news feeds and article pages

- URL: https://openai.com/news/rss.xml
- Date checked: 2026-06-08
- Search terms checked: project README and source configuration
- License: public feed/page content, not vendored source
- Version / commit: not applicable
- Adoption mode: `direct-dependency`
- Why relevant: the app watches public news sources and summarizes public article bodies.
- Decision: keep source-specific adapters instead of one generic scraper.
- Integration plan: source adapters live under `src/sources/`; fixture tests cover expected parsing behavior.
- Maintenance risk: RSS shape, page structure, or publishing URLs may change.
- Security notes: do not mix private/authenticated content into summaries or docs.
- Recheck when: source fixtures fail or feed/page structure changes.

## Copied source requirements

If `vendored-source` is used, also record:

- Exact source URL:
- Commit hash:
- License:
- Files copied:
- Modifications:
- Owner:
- Update plan:
- Personal-only? yes/no
- External sharing / redistribution review needed? yes/no

## Rules

- Prefer `reference-only`, `concept-only`, `direct-dependency`, or `adapter`.
- Do not add dependencies without a maintenance/security check.
- Do not copy source unless provenance and license are recorded.
- Re-check license obligations before publishing, sharing externally, using for company work, or redistributing copied source.
