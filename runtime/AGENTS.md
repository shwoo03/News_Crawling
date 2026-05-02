# Runtime Rules

- Runtime ledgers are append-only evidence; do not rewrite history to hide failures.
- Redact secrets before logging activity, tool output, completion evidence, or handoff text.
- Use session/runtime locks for writers that append to ledgers or update snapshots.
- SQLite/session indexes are cache files; JSONL and Markdown ledgers remain the source of truth.
- Closeout evidence must distinguish genuine success from partial progress and residual risk.
- Do not copy runtime state into a new project as if it were project truth.

