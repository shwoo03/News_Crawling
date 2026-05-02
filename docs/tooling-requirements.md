# Tooling Requirements

The harness is standard-library first. These tools are recommended for full operation:

- Python 3.11 or newer for `scripts/*.py`.
- Git for checkpoint metadata and reference review.
- Codex CLI and/or Claude Code for agent operation.
- Optional: `jq` for ad hoc JSON inspection.
- Optional: Node/npm only when the target project includes `package.json` checks.

Do not hardcode machine-local paths in reusable templates. Run `python3 scripts/portability-scan.py --root .` before distributing or copying the skeleton.
