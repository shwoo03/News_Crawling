---
name: research
intent: Reference-first investigation before implementation.
public: true
maps_to: python3 scripts/agent-flow.py research --auto --goal "<user goal>" --format json
write_policy: read_only
requires_confirmation: false
---

# /research

Reference-first investigation. The agent should start with preview mode:

`python3 scripts/agent-flow.py research --auto --goal "<user goal>" --format json`

Only create cards or proposals after the user approves the write path.
