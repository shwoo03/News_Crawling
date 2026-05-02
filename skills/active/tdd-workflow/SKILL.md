---
name: tdd-workflow
description: Use when implementing behavior that can be specified with tests, examples, or validation checks.
---

<!-- Body target: <=500 lines. Link to data/ or external/ for detail. -->

# TDD Workflow

## When to Activate

Use this skill for implementation, bug fixes, behavior changes, and validation
planning.

## Workflow

1. Define expected behavior.
2. Find or create the narrowest validation.
3. Implement the smallest change.
4. Run the relevant check.
5. Record evidence in `runtime/activity-log.jsonl` when the result affects a
   decision.

## Trigger Examples

- A behavior change needs a clear pass/fail check.
- A bug fix can be reproduced.
- A validation scenario can be expressed as examples.
- A project has no test harness but needs manual validation.

## Output Shape

- Expected behavior.
- Smallest validation.
- Implementation scope.
- Verification result.

## References

- `../../../rules/common/tdd-workflow.md`
- `../../../runtime/validation/README.md`
