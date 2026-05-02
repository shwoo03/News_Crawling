---
name: security-review
description: Use when changes touch permissions, credentials, automation, memory, network, or generated code execution.
---

<!-- Body target: <=500 lines. Link to data/ or external/ for detail. -->

# Security Review

## When to Activate

Use this skill for auth, secrets, permissions, automation, sandboxing, and data
handling.

## Workflow

1. Identify sensitive assets and write scopes.
2. Check whether the action changes permissions or automation behavior.
3. Confirm generated changes remain dry-run unless approved.
4. Verify no secrets or sensitive data are logged.
5. Escalate boundary changes.

## Trigger Examples

- Editing auth, permissions, secrets, or network access.
- Changing automation from dry-run to apply.
- Writing memory extracted from user/project data.
- Creating scripts that execute generated code.

## Output Shape

- Sensitive assets identified.
- Permission boundary.
- Risk rating.
- Required approval or safe default.

## References

- `../../../rules/common/security-review.md`
- `../../../docs/GOVERNANCE.md`
