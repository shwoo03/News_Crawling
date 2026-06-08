# AI Project Kit Merge Plan

## Existing project facts

- Stack: Node.js, TypeScript, Playwright, Node built-in SQLite, Docker Compose.
- Existing agent instruction files: `AGENTS.md`, nested `docs/AGENTS.md`, `runtime/AGENTS.md`, `scripts/AGENTS.md`, `skills/AGENTS.md`, plus existing `.claude/skills` and `.codex/skills` surfaces.
- Existing validation commands: `npm test`, `python3 scripts/verify-skeleton.py`, `python3 scripts/verify.py`, `python3 scripts/quality-gate.py --format json`.
- Existing automation surfaces: `runtime/`, `hooks/`, `mcp/`, `.agents/`, `.claude/`, `.codex/`, `skills/`, `agents/`, and CI workflow.
- Known failure modes: missing secrets, repeated delivery of already-seen articles, source page/RSS shape drift, summarizer JSON/length failure, Discord webhook delivery failure, and over-heavy agent operating surfaces becoming confused with app runtime.
- Existing regression checks or debug notes: TypeScript node tests under `tests/*.test.ts`, Python operational tests under `tests/test_*.py`, and project docs under `docs/`.

## Starter-kit sections to merge

- `AGENTS.md`: preserve existing project-specific Korean operating guide. Do not replace it with the generic template.
- `docs/PROJECT_PROFILE.md`: preserve existing filled profile.
- `docs/SECURITY.md`: add missing canonical security summary focused on Groq, Discord, SQLite, external news sources, and agent tool boundaries.
- `docs/HANDOFF.md`: add missing current-state handoff for this adoption pass.
- `docs/REFERENCES.md`: add missing project-specific adoption/reference decisions.
- `docs/LINKS.md`: add missing official link registry for this project.
- `docs/PROFILE_CHECKLIST.md`: add missing legacy-upgrade checklist with this repo's existing optional surfaces marked as already present.

## Conflicts

- Existing rule: the project already has a large agent operating skeleton with runtime logs, hooks, skills, subagents, MCP config, and ledgers.
- Starter-kit rule: the current AI Project Kit keeps the default surface small and treats optional operating surfaces as explicitly adopted.
- Resolution: do not delete existing surfaces in this pass. Record them as existing project-owned surfaces and avoid adding more by default.

## Optional surfaces

- Hooks: already present under `hooks/` and `scripts/hooks/`; do not add new hooks in this pass.
- Skills: already present under `skills/`, `.claude/skills`, and `.codex/skills`; do not add new skills in this pass.
- Subagents: already present under `.agents/subagents` or similar surfaces; do not add new subagents in this pass.
- MCP: already present under `mcp/servers.yaml`; do not add servers in this pass.
- Plugins: already present under `.agents/plugins`, `.claude-plugin`, and `.codex-plugin`; do not package new plugins in this pass.
- Runtime: app runtime is `src/`; agent operating runtime also exists under `runtime/`.
- Project memory: not added in this pass.
- Research archive: already present under `research/`; preserve.

## Validation

- Commands to run: `npm test`, `python3 scripts/verify-skeleton.py`, and `git diff --check`.
- Expected result: tests and skeleton checks pass, or failures are recorded in `docs/HANDOFF.md`.
- Known failure modes to preserve: source drift, duplicate delivery, missing secret handling, summarizer malformed output, delivery failure, and over-heavy agent surface confusion.
- Regression checks to run or add: keep `tests/*.test.ts` for source adapters and app behavior; use `docs/HANDOFF.md` to record any validation that cannot run.
