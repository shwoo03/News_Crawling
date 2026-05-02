---
name: start
intent: Natural-language routing and project status triage.
public: true
maps_to: python3 scripts/agent-flow.py start --goal "<user goal>" --format json
write_policy: read_only
requires_confirmation: false
---

# /start

Natural-language entrypoint. The agent should run:

`python3 scripts/agent-flow.py start --goal "<user goal>" --format json`

Use the returned mode, questions, write policy, and next command to continue the conversation.
