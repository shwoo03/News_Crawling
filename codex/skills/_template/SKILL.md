---
name: replace-with-skill-name
description: Replace with a narrow description of when this skill applies.
---

# Skill Name

## When to Activate

Use this skill when:

- The task clearly matches this domain or workflow.
- The user explicitly asks for this skill.

Do not use this skill when:

- The task is unrelated to this domain.
- A smaller local read or edit is sufficient.

## Workflow

1. Read the project profile.
2. Load only the relevant files from `data/`.
3. Load `external/` references only when needed.
4. Produce a bounded result with evidence.
5. Record reusable lessons as proposals, not direct edits.

## References

- `data/checklist.md`
- `external/README.md`

## Safety

- Keep `SKILL.md` concise.
- Do not auto-edit this file.
- Generated lessons belong under `external/auto-lessons/`.
