# Legacy project upgrade checklist

This checklist records how the current AI Project Kit skeleton was applied to the existing News_Crawling repository.

## Profile

- [x] Existing project path used.
- [x] `legacy-project-upgrade` reference scaffold generated outside the repository.
- [x] Existing README, AGENTS, docs, package scripts, CI, and source files were read before editing.
- [x] Existing project-specific rules were preserved.
- [x] Missing canonical docs were added instead of running scaffold directly in the target.

## Canonical docs

- [x] `AGENTS.md` exists and remains project-specific.
- [x] `docs/PROJECT_PROFILE.md` exists and remains filled.
- [x] `docs/HANDOFF.md` added.
- [x] `docs/SECURITY.md` added.
- [x] `docs/REFERENCES.md` added.
- [x] `docs/LINKS.md` added.
- [x] `docs/PROFILE_CHECKLIST.md` added.

## Existing optional surfaces

These surfaces already existed before this adoption pass. They are not new default scaffold output from this pass.

- [x] Runtime / app code: `src/`
- [x] Agent operating runtime: `runtime/`
- [x] MCP config: `mcp/`
- [x] Hooks: `hooks/`, `scripts/hooks/`
- [x] Skills: `skills/`, `.claude/skills`, `.codex/skills`
- [x] Subagents / agent surfaces: `.agents/`, `agents/`, `codex/agents/`
- [x] Plugins: `.agents/plugins`, `.claude-plugin`, `.codex-plugin`
- [x] Research archive: `research/`
- [ ] Project memory: not added in this pass

## Validation

- [ ] `npm test` failed before tests started: Node `v26.0.0` reported `node: bad option: --experimental-transform-types`.
- [x] `python3 scripts/verify-skeleton.py` passed with warnings.
- [x] `git diff --check` passed.

Record actual validation evidence in `docs/HANDOFF.md` after running checks.

## Boundary decision

The current AI Project Kit default is small, but this repository already contains heavier operating surfaces. This pass records them as existing project-owned choices and does not remove them.

Future cleanup should be a separate explicit task with a rollback plan.
