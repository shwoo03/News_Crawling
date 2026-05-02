#!/usr/bin/env python3
"""Report repeated tool-call failures from activity logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


FAIL_STATUSES = {"failure", "timeout", "unknown"}
WARN_AT = 2
BLOCK_AT = 3
HALT_AT = 5


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_events(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / "runtime" / "activity-log.jsonl"
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    findings: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"runtime/activity-log.jsonl:{line_no} invalid JSON: {exc}")
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            findings.append(f"runtime/activity-log.jsonl:{line_no} event must be an object")
    return events, findings


def stable_resource(call: dict[str, Any]) -> str:
    for key in ("resource", "path", "command", "name", "target"):
        value = call.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    args = call.get("args") or call.get("arguments") or call.get("input")
    if isinstance(args, (dict, list, str)):
        raw = json.dumps(args, ensure_ascii=False, sort_keys=True) if not isinstance(args, str) else args
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
    return "unknown"


def normalized_status(call: dict[str, Any]) -> str:
    raw = str(call.get("normalized_status") or call.get("status") or "").lower()
    if raw in {"failed", "fail", "error"}:
        return "failure"
    if raw in {"timed_out", "timed-out"}:
        return "timeout"
    return raw or "unknown"


def action_for_count(count: int) -> str:
    if count >= HALT_AT:
        return "halt"
    if count >= BLOCK_AT:
        return "block"
    if count >= WARN_AT:
        return "warn"
    return "allow"


def analyze(root: Path) -> dict[str, Any]:
    events, findings = read_events(root)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for index, event in enumerate(events, start=1):
        call = event.get("tool_call")
        if not isinstance(call, dict):
            continue
        status = normalized_status(call)
        if status not in FAIL_STATUSES:
            continue
        tool = str(call.get("tool") or "unknown")
        failure_type = str(call.get("failure_type") or status)
        groups[(tool, stable_resource(call), failure_type)].append({"index": index, "ts": event.get("ts") or event.get("timestamp") or ""})

    repeated: list[dict[str, Any]] = []
    for (tool, resource, failure_type), items in sorted(groups.items()):
        count = len(items)
        action = action_for_count(count)
        if action == "allow":
            continue
        repeated.append(
            {
                "tool": tool,
                "resource": resource,
                "failure_type": failure_type,
                "count": count,
                "action": action,
                "events": items[-5:],
            }
        )
    return {"ok": not findings, "findings": findings, "repeated_failures": repeated}


def output(value: Any, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        if value.get("findings"):
            print("tool guardrail findings:")
            for finding in value["findings"]:
                print(f"  ERROR {finding}")
        if not value.get("repeated_failures"):
            print("no repeated tool failures.")
        for item in value.get("repeated_failures", []):
            print(f"{item['action'].upper()} {item['tool']} {item['resource']} {item['failure_type']} x{item['count']}")


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    payload = analyze(root)
    output(payload, args.format)
    if payload["findings"]:
        return 1
    if args.strict and any(item["action"] in {"block", "halt"} for item in payload["repeated_failures"]):
        return 1
    return 0


def cmd_summary(root: Path, args: argparse.Namespace) -> int:
    output(analyze(root), args.format)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("summary").set_defaults(func=cmd_summary)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    return args.func(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
