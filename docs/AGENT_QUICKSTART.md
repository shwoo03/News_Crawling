# Agent Quickstart

## First 5 Minutes

1. Read `AGENTS.md`.
2. Run `python3 scripts/agent-flow.py start --goal "<user goal>" --format json`.
3. Check `mode`, `next_command`, `next_action_type`, `requires_confirmation`, and `signals`.
4. Ask only the questions needed to remove ambiguity.
5. Continue through reference, build, decide, or closeout according to the routed mode.

## New Project

For “새 프로젝트 시작해줘” style requests, start with `agent-flow start`. If the route is `research`, preview references first with the returned command, including `--goal`. Write candidate cards or proposals only after the user approves that direction.

## Build Requests

For “이 기능 구현해줘” style requests, use the returned `build_intake` before editing. Lock the implementation scope and acceptance criteria in conversation, then create `plans/active/<seq>-<slug>.md` after approval.

## Maintenance Audit

For “우리 뼈대 개선해줘” requests, classify whether the goal is pure maintain work or reference-backed maintain work. If the goal mentions ECC, opencode, benchmarks, mature references, or comparison, use the reference review path before editing.

## Reference Adoption

Use candidate cards and proposals as the evidence trail. Do not add dependencies, copy code, or promote a skill without a review queue decision when policy requires confirmation.

## Closeout

Closeout is a write-with-confirmation flow because it records completion evidence and session state. Run `python3 scripts/verify.py`, `python3 scripts/quality-gate.py --format json`, and record evidence only when the gate is genuinely passing or explicitly marked as partial progress with residual risk.
