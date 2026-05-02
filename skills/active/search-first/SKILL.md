---
name: search-first
description: Use when starting a task, entering a new codebase, or making architecture decisions that should respect existing project facts.
---

<!-- Body target: <=500 lines. Link to data/ or external/ for detail. -->

# Search First

## When to Activate

Use this skill before designing, refactoring, debugging, or creating project
structure.

## Workflow

1. Read `docs/PROJECT_PROFILE.md` if it exists.
2. Search relevant files with targeted queries.
3. Identify existing conventions and conflicts.
4. Summarize the facts that constrain the next step.
5. Proceed only after repo facts are known.

## Trigger Examples

- "Add a feature to this repo" with unknown structure.
- "Refactor this module" before conventions are known.
- "Document this system" before source docs are inspected.
- "Which file controls X?" when search can answer it.

## Output Shape

- Existing conventions found.
- Files or docs that constrain the task.
- Conflicts or missing facts.
- Recommended next action.

## References

- `../../../rules/common/search-first.md`
