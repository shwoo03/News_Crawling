# Wiki Query Workflow

Purpose: retrieve human-curated knowledge with bounded context.

## Inputs

- Current task.
- `knowledge/index.md`.
- Referenced knowledge files.
- Active skills.

## Process

1. Start with `knowledge/index.md`.
2. Select relevant entries only.
3. Open referenced files only when needed.
4. Return source pointers with any injected context.

## Output

- Bounded context summary.
- Source pointers.
- Uncertainty notes.

## Acceptance Criteria

- Query starts from the index.
- Context is relevant to the current task.
- Agents do not modify `knowledge/`; they may propose changes only.
