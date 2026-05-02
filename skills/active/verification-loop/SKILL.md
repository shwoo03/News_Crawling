---
name: verification-loop
description: Use before claiming work is done or after generating files, structured data, docs, or code.
---

<!-- Body target: <=500 lines. Link to data/ or external/ for detail. -->

# Verification Loop

## When to Activate

Use this skill before finalizing a task.

Use especially when:

- Files, docs, or structured artifacts were generated.
- JSON, JSONL, YAML, TOML, Markdown links, or templates changed.
- The user asked for implementation, not only analysis.
- A prior step produced a proposal, validation result, or memory candidate.

Do not use when:

- The task was pure conversation with no claims that require evidence.
- The user explicitly asks not to run checks.

## Workflow

1. List expected outputs.
2. Check that required files or artifacts exist.
3. Parse structured files.
4. Run available tests or checks.
5. Report what passed and what could not be verified.

## Verification Matrix

| Artifact | Minimum Check |
| --- | --- |
| Markdown docs | Required files exist; key links/paths are real where local. |
| JSON/JSONL | Parse every line/object. |
| Templates | Required placeholders and instructions exist. |
| Runtime logs | Append-only format remains valid JSONL. |
| Skills | YAML frontmatter has `name` and `description`; body stays bounded. |
| Notion docs | DB page created/updated; no nested pages. |

## Output Shape

- Checked artifacts.
- Commands or tools used.
- Passed checks.
- Failed or skipped checks.
- Residual risk.

## References

- `../../../rules/common/verification-loop.md`
- `data/checklist.md`
- `data/examples/verification-report.md`
