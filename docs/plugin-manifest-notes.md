# Plugin Manifest Notes

This skeleton keeps plugin metadata lightweight and generated-client neutral.

- `.codex-plugin/plugin.json` describes the Codex-facing package surface.
- `.claude-plugin/plugin.json` describes the Claude-facing package surface.
- `.agents/plugins/marketplace.json` lists installable local plugin entries.
- Plugin entrypoints must stay inside the repo and point at the appropriate agent rules file.
- Generated `.codex/` and `.claude/` artifacts remain build outputs; update canonical files first.

Validate plugin metadata with:

```bash
python3 scripts/plugin-manifest-check.py --root . check
```

`scripts/schema-check.py` also validates the shared manifest field contract
against `schemas/plugin-manifest.schema.json`. Use `plugin-manifest-check.py`
for marketplace/cross-file consistency and `schema-check.py` for schema drift.
