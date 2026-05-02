---
name: decide
intent: Human decision synchronization for proposals and review queue items.
public: true
maps_to: python3 scripts/agent-flow.py decide --proposal <proposal-path> --decision accepted|rejected|deferred --by <name> --format json
write_policy: read_only
requires_confirmation: true
---

# /decide

Human decision synchronization for review queue items and proposals.

Use `agent-flow start` first to identify the pending proposal, then run `agent-flow decide` with `accepted`, `rejected`, or `deferred`.
