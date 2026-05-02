---
name: closeout
intent: Verification and completion evidence after approved implementation.
public: true
maps_to: python3 scripts/agent-flow.py closeout --goal "<goal>" --changed-path <path> --format json
write_policy: write_with_confirmation
requires_confirmation: true
---

# /closeout

Verification and completion evidence flow.

The agent should run `agent-flow closeout` after implementation, with the task goal, changed paths, and any skills used.
