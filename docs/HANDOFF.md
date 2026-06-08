# Handoff

## Session metadata

- Date: 2026-06-08
- Branch: `main`
- Latest checked commit: `5ebee48 chore: record env history purge`
- Goal: apply the current AI Project Kit skeleton to the existing News_Crawling repository without overwriting local rules.
- Handoff stale? no

## Current state

- News_Crawling is a Node.js/TypeScript worker that watches AI news sources, summarizes article bodies with Groq, stores seen URLs in SQLite, and sends Discord webhook briefings.
- The repository already had a large agent operating skeleton: `runtime/`, `hooks/`, `mcp/`, `skills/`, `.claude/`, `.codex/`, `.agents/`, `agents/`, and many docs.
- This pass added the missing lightweight canonical docs instead of replacing the existing operating guide.
- Existing `AGENTS.md`, `README.md`, source files, tests, CI, and package scripts were preserved.

## Next action

Run validation and decide whether the older heavy operating surfaces should remain, be documented as intentionally adopted, or be slimmed in a separate cleanup pass.

## Next smallest action

Run:

```bash
npm test
python3 scripts/verify-skeleton.py
git diff --check
```

## Blockers / unknowns

- Some existing CI commands are Python-oriented even though the app runtime is Node.js/TypeScript.
- Current local Node `v26.0.0` does not accept the package script flag `--experimental-transform-types`, so `npm test` cannot start in this environment without adjusting the runtime or script.
- The repository contains many optional agent operating surfaces that are outside the current small default kit.
- Live Discord delivery requires real secrets and should not be tested without explicit user approval.

## Evidence

- Reference scaffold generated outside the project at `/private/tmp/ai-project-kit-reference-news-crawling`.
- Project git status before edits: clean on `main...origin/main`.
- Latest checked commit: `5ebee48 chore: record env history purge`.
- Existing project docs/source inspected: `README.md`, `AGENTS.md`, `docs/PROJECT_PROFILE.md`, `package.json`, CI workflow, `.env.example`, and core `src/` modules.
- Added canonical docs: `docs/AI_PROJECT_KIT_MERGE_PLAN.md`, `docs/SECURITY.md`, `docs/HANDOFF.md`, `docs/REFERENCES.md`, `docs/LINKS.md`, `docs/PROFILE_CHECKLIST.md`.
- Generated Claude adapter `CLAUDE.md` and `.claude/skills/claude-md-rules-skills/SKILL.md`; both are currently ignored by this repository `.gitignore`.
- Validation run: `npm test` failed before tests started because Node `v26.0.0` reported `node: bad option: --experimental-transform-types`.
- Validation run: `python3 scripts/verify-skeleton.py` passed with warnings for `scripts/__pycache__` and 3 portability findings.
- Validation run: `git diff --check` passed.

## Decisions made

- Treat this as an existing-project adoption, not a new scaffold.
- Preserve the existing Korean `AGENTS.md` because it contains project-specific operating policy.
- Do not run scaffold helpers directly inside this repository.
- Do not add new hooks, MCP servers, skills, subagents, plugins, runtime ledgers, or project memory in this pass.
- Record existing optional surfaces instead of removing them.

## Promote to stable docs?

- AGENTS.md: no direct replacement in this pass.
- PROJECT_PROFILE.md: already filled; no direct change in this pass.
- SECURITY.md: added.
- REFERENCES.md: added.
- PROJECT_MEMORY.md: not added.
- research/: existing research directory preserved.

## Notes

- If this project should become a small, app-focused repo instead of an agent operating skeleton, do that as a separate cleanup with explicit approval and a rollback plan.
