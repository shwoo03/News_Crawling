# Skills Rules

- Canonical project skills live under `skills/active/`; candidates and meta skills stay in their own roots.
- Do not edit `.codex/skills` or `.claude/skills` directly.
- Add or update `goldens/*.yaml` when a skill behavior is verifiable.
- Keep skill names unique across `skills/active`, `skills/_candidates`, and `skills/_meta`.
- Run `python3 scripts/eval-all.py --format json` after skill changes.
- Promotion or demotion remains proposal-only unless the user confirms.

