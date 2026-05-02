# Skill Architecture

Skills package reusable project knowledge and workflows. This repository uses
the Claude Code `SKILL.md` schema as the shared skill format.

## Directory Roles (single source of truth)

| Directory | Role |
| --- | --- |
| `<project>/skills/active/` | **Canonical location for active skill content.** All working skills live here and are transformed into runtime artifacts by `scripts/convert.py`. |
| `<project>/.codex/skills/`, `<project>/.claude/skills/` | Generated runtime artifacts. Do not edit directly. Regenerate from `skills/active/`. |
| `codex/skills/` | **Documentation and templates only.** Explains the skill model for Codex and houses `_template/` for new skills. Does not contain runnable skills. |
| `~/.claude/skills/` | User-global personal skills, managed outside this skeleton. |

Codex and Claude consume generated skill files that come from the same
canonical source. Do not duplicate skill bodies into `codex/skills/`.

## Rules vs Skills (relationship)

Rules (`rules/common/*.md`, `rules/languages/*.md`) define **WHAT must be true**
— invariants, guardrails, prohibitions. Skills (`skills/active/*/SKILL.md`)
define **HOW to do the work** — triggers, step-by-step workflow, data
references, output shape.

When a topic appears in both (for example "search-first" has `rules/common/search-first.md`
and `skills/active/search-first/SKILL.md`):

- The **rule** states the non-negotiable condition ("search before inventing").
- The **skill** states the procedure for meeting the rule (when to activate,
  which steps to run, what to return).
- Both remain active. The skill refers back to the rule as its precondition;
  the rule does not need to know about the skill.

## Language convention

`rules/*.md` is written in the project's primary natural language (Korean in
this skeleton). `skills/active/*/SKILL.md` stays in English because SKILL.md
is consumed by agents/tools that rely on English frontmatter and trigger
descriptions for activation. This split is intentional; do not translate
SKILL.md bodies into Korean.

## 3-Depth Structure

```text
<project>/skills/active/<skill-name>/
  SKILL.md
  data/
  external/
```

## Depth 1: `SKILL.md`

Keep this file short. It should contain:

- Name.
- Description.
- When to activate.
- Workflow summary.
- Pointers to detailed files.
- Safety boundaries.

Do not put large references or long examples in `SKILL.md`.

## Depth 2: `data/`

Use this for project-owned, maintained knowledge:

- Checklists.
- Patterns.
- Examples.
- Playbooks.
- Decision tables.

Files here may be edited by humans during normal project work.

## Depth 3: `external/`

Use this for bulky or generated material:

- External source notes.
- Imported references.
- Auto-lessons.
- Large examples.
- Evaluation traces.

Generated content belongs here, not in `SKILL.md`.

## Activation Rules

A skill should activate when:

- The user explicitly names the skill.
- The task matches the skill description.
- A file path or domain condition in the skill says it applies.

Avoid broad descriptions that cause every task to activate the skill.

## Template

Use `skills/_templates/SKILL.template.md` as the starting point for new skills,
then create the skill under `skills/active/<skill-name>/` or
`skills/_candidates/<skill-name>/`. Regenerate runtime artifacts with
`python3 scripts/convert.py` when the canonical skill surface changes.
