# Wiki Lint Workflow

Purpose: detect knowledge drift before stale or contradictory entries mislead
agents.

## Inputs

- `knowledge/index.md`
- `knowledge/log.md`
- `knowledge/project-registry.md`
- Accepted knowledge files.

## Checks

- Stale: no review or update for 180 days.
- Duplicate: same topic or dedupe key appears in multiple accepted entries.
- Superseded: an entry is replaced but not marked.
- Source pointer: each index entry includes at least one source pointer
  (`activity-log` ts, `file:line`, or URL).
- Supersession metadata: `superseded_by` and `superseded_at` must appear
  together, and referenced IDs must exist.
- Orphan: index points to missing content.
- Contradiction: accepted entries make incompatible claims.
- Wikilink broken: a knowledge body contains `[[Kxxx]]` that does not match any
  `entry_id` in `index.md`. Use only for cross-references; the index itself
  must use the ID column, not wikilinks.
- Graph gaps: accepted knowledge files can be reported as isolated, weakly
  linked, or bridge candidates. These are review hints, not automatic failures.

## Output

- Updated `knowledge/lint-report.md`.
- Proposals for archive, merge, or correction.

## Acceptance Criteria

- Lint does not delete knowledge.
- Every finding includes source pointers.
- Findings become review targets or proposals.
