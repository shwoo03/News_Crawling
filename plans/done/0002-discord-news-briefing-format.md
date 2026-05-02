# Plan 0002: Discord News Briefing Format

- `status`: done
- `goal`: OpenAI, Anthropic, Threads Discord messages use a structured Korean news briefing format.
- `acceptance`: summaries include lead, two summary sentences, four highlights, two importance bullets, source, and published time.
- `verification`: Docker build, Docker one-off top/latest run, focused unit tests for summarizer and Discord payload.

## Implementation Notes

- Keep the current source adapters and delivery flow.
- Add structured summary fields while preserving `summaryKo` and `charCount` for existing logging.
- Render Discord embeds with briefing title and Korean field labels.
- Keep webhook masking behavior unchanged.

## Completion Evidence

- `docker compose build news-crawler`: passed.
- `docker compose run --rm --no-deps -v /Users/shwoo/mydir/Project/News_Crawling/src:/app/src:ro -v /Users/shwoo/mydir/Project/News_Crawling/tests:/app/tests:ro news-crawler node --experimental-transform-types --test tests/*.test.ts`: 15 passed, 0 failed.
- `docker compose run --rm --no-deps news-crawler node --experimental-transform-types src/index.ts --top --latest`: OpenAI, Anthropic, and Threads all reported `deliveryStatus=sent`.
