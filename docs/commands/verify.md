---
name: verify
intent: Direct validation shim for focused debugging and CI checks.
public: false
maps_to: python3 scripts/verify.py --root .
write_policy: read_only
requires_confirmation: false
---

# /verify

Validation command shim for agents.

Use `python3 scripts/verify.py --root .` for the canonical check, lint, unit, smoke, and integration sequence. Use `quality-gate.py` only for focused debugging or closeout internals.
