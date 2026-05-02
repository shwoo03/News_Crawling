# Security Boundary

This harness uses permissions and confirmation gates to reduce accidental risk, but those gates are not a sandbox boundary.

- Treat CLI permissions as workflow controls, not isolation.
- Do not store secrets in prompts, plans, logs, runtime ledgers, or reference cards.
- Keep real tokens in environment variables or a secret manager.
- Run copied reference code only after review, malware/audit checks, and user confirmation.
- Generated `.codex/` and `.claude/` artifacts should be regenerated from canonical sources, not hand-edited.

If a secret is exposed, rotate it immediately and append the incident and rotation decision to `state/decisions.md`.
