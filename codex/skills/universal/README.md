# Universal Skills

Canonical universal skill seeds live in project `skills/active/`.
`scripts/convert.py` generates `.codex/skills/` and `.claude/skills/` artifacts
from that source so both runtimes see the same skill surface.

Included skills:

- `skills/active/search-first/SKILL.md`
- `skills/active/tdd-workflow/SKILL.md`
- `skills/active/verification-loop/SKILL.md`
- `skills/active/security-review/SKILL.md`

Do not duplicate skill bodies here. Keep this directory as a Codex-facing index
to the shared project skill surface.
