# Scripts Rules

- Public entrypoint stays `scripts/agent-flow.py`; all other scripts are internal tools.
- Prefer standard library implementations and avoid adding dependencies.
- Keep write operations dry-run or explicit-flag based unless called from approved closeout/decision flow.
- Update `scripts/catalog.yaml` when adding or changing an internal tool.
- Run `python3 -m unittest discover -s tests -v` and `python3 scripts/verify.py` after behavior changes.
- Do not write generated `.codex/` or `.claude/` artifacts directly.

