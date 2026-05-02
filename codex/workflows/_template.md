# Workflow Template

## Metadata

- `workflow_name`:
- `status`: draft
- `owner_agent`:
- `version`: 0.1
- `last_reviewed`:

## Objective

Describe the repeatable job this workflow performs.

## Trigger

When should this workflow run?

Examples:

- New project profile created.
- Validation fails.
- Session ends.
- Weekly project review date arrives.
- User explicitly requests the workflow.

## Input Sources

- `docs/PROJECT_PROFILE.md`
- `docs/ARCHITECTURE.md`
- `runtime/activity-log.jsonl`
- Other project-specific sources:

## Process

1. Confirm the trigger.
2. Load only required input sources.
3. Check permissions.
4. Execute the bounded task.
5. Validate the output.
6. Log the run.
7. Create proposals for any system changes.

## Tools Required

- Read:
- Search:
- Edit:
- Test:
- External tools:

## Permissions

- Read scope:
- Write scope:
- Proposal scope:
- Approval required for:

## Stop Conditions

- Missing project profile.
- Permission boundary exceeded.
- Validation method undefined.
- Required input source unavailable.

## Escalation Conditions

- Repeated failure.
- Conflicting memory.
- Scope expansion needed.
- Pivot trigger fired.

## Output Artifacts

- Primary output:
- Logs:
- Proposals:
- Validation result:

## Validation Method

Define how to decide whether this workflow succeeded.

## Logging Required

- Append a run record to `runtime/agent-runs.jsonl`.
- Append major decisions to `runtime/activity-log.jsonl`.
