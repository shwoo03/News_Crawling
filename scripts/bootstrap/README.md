# Bootstrap Scripts

This directory contains scripts that create a new project from this skeleton.
The v1 command is `new-project.py`.

## Contract

Input:

- Project name.
- Destination path.
- Optional domain and stack.

Command:

```powershell
python scripts/bootstrap/new-project.py --name <project-name> --target <path> [--domain <domain>] [--stack <stack>] [--force]
```

`--name` constraints (enforced by `_validate_name` in `new-project.py`):

- Non-empty; max 200 characters.
- Must not contain `|`, newline, carriage return, tab, NUL, or path separators (`/` `\`).
  The name is embedded literally in `knowledge/index.md` table cells and in the
  `project` field of `runtime/activity-log.jsonl`, so these characters would
  corrupt Markdown tables, JSONL lines, or downstream file paths.

`--domain`, `--stack`, `--owner` must be single-line (no newline / carriage
return / NUL) because they are seeded into single-line Markdown bullets in
`docs/PROJECT_PROFILE.md`.

Output:

- Skeleton copied to destination.
- `docs/PROJECT_PROFILE.md` created as the only required project file.
- `docs/PROJECT_SPEC.md` is not created automatically; agents draft it later
  only if implementation needs a correctness contract.
- First `runtime/activity-log.jsonl` entry appended.

Safety:

- Refuse to use the skeleton root as the destination.
- Refuse to merge into a non-empty destination unless `--force` is passed.
- Avoid copying `.git`, `.codex`, caches, and existing runtime JSONL logs.
- Preserve runtime-owned config boundaries.
- Print a summary of created files.
