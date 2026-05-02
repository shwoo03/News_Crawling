# Docs Rules

- Keep `AGENTS.md`, `scripts/catalog.yaml`, and docs command shims aligned.
- Use `python3` in examples.
- Mark generated/runtime paths as artifacts, not canonical sources.
- Command docs under `docs/commands/` require frontmatter metadata.
- After structural doc changes, run `python3 scripts/verify-skeleton.py --skip-wiki-lint`.
- Do not describe internal scripts as user-facing commands unless `scripts/catalog.yaml` marks them public.

