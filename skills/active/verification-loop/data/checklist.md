# Verification Loop Checklist

Use this as the golden reference for new skills.

## Scope

- [ ] Expected outputs are listed.
- [ ] Changed files or external artifacts are known.
- [ ] Validation level is appropriate for the task.

## File Checks

- [ ] Required files exist.
- [ ] Generated directories exist.
- [ ] Local doc paths referenced by the answer are valid.
- [ ] No protected runtime-owned files were edited unexpectedly.

## Structured Data Checks

- [ ] JSON files parse.
- [ ] JSONL files parse line by line.
- [ ] YAML/TOML frontmatter or config parses where applicable.
- [ ] Required schema fields are present.

## Skill Checks

- [ ] `SKILL.md` has `name` and `description`.
- [ ] Skill body remains below the 500-line target.
- [ ] Detailed references are linked from `data/` or `external/`.
- [ ] Trigger examples are concrete enough to guide activation.

## Runtime Checks

- [ ] `runtime/activity-log.jsonl` remains append-only and parseable.
- [ ] `runtime/agent-runs.jsonl` remains parseable if touched.
- [ ] Proposals remain in `runtime/proposals/`.
- [ ] `knowledge/` edits are human-driven, not agent-written.

## Reporting

- [ ] State what passed.
- [ ] State what could not be verified.
- [ ] State residual risks.
