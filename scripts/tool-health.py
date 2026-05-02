#!/usr/bin/env python3
"""Summarize and validate normalized tool-call health from activity logs."""

from __future__ import annotations

import argparse
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


KNOWN_STATUSES = {"success", "failure", "timeout", "skipped", "empty", "unknown"}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def log_path(root: Path) -> Path:
    return root / "runtime" / "activity-log.jsonl"


def normalize_status(status: str, summary: str = "", data: Any = None) -> str:
    raw = (status or "").strip().lower()
    if raw in {"ok", "success", "succeeded", "completed", "pass", "passed"}:
        normalized = "success"
    elif raw in {"fail", "failed", "failure", "error", "errored"}:
        normalized = "failure"
    elif raw in {"timeout", "timed_out", "timed-out"}:
        normalized = "timeout"
    elif raw in {"skip", "skipped"}:
        normalized = "skipped"
    else:
        normalized = "unknown"
    if normalized == "success" and not str(summary or "").strip() and not data:
        return "empty"
    return normalized


def read_events(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = log_path(root)
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
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} event must be an object")
            continue
        events.append(value)
    return events, findings


def tool_call(event: dict[str, Any]) -> dict[str, Any] | None:
    value = event.get("tool_call")
    return value if isinstance(value, dict) else None


def build_summary(root: Path) -> dict[str, Any]:
    events, findings = read_events(root)
    tools: dict[str, dict[str, Any]] = {}
    for event in events:
        call = tool_call(event)
        if not call:
            continue
        name = str(call.get("tool") or "unknown")
        status = str(call.get("normalized_status") or normalize_status(str(call.get("status") or ""), str(call.get("summary") or ""), event.get("data")))
        bucket = tools.setdefault(
            name,
            {
                "tool": name,
                "calls": 0,
                "success": 0,
                "failure": 0,
                "timeout": 0,
                "skipped": 0,
                "empty": 0,
                "unknown": 0,
                "sidecars": 0,
                "duration_ms_total": 0.0,
            },
        )
        bucket["calls"] += 1
        bucket[status if status in KNOWN_STATUSES else "unknown"] += 1
        if call.get("sidecar_path"):
            bucket["sidecars"] += 1
        duration = call.get("duration_ms")
        if isinstance(duration, (int, float)) and duration >= 0:
            bucket["duration_ms_total"] += float(duration)
    for bucket in tools.values():
        calls = int(bucket["calls"])
        bucket["success_rate"] = round(float(bucket["success"]) / calls, 4) if calls else 0.0
        bucket["failure_rate"] = round(float(bucket["failure"] + bucket["timeout"]) / calls, 4) if calls else 0.0
        bucket["duration_ms_avg"] = round(float(bucket.pop("duration_ms_total")) / calls, 3) if calls else 0.0
    return {
        "path": log_path(root).as_posix(),
        "findings": findings,
        "tools": sorted(tools.values(), key=lambda item: str(item["tool"])),
    }


def validate(root: Path) -> tuple[list[str], dict[str, Any]]:
    payload = build_summary(root)
    findings = list(payload["findings"])
    events, _ = read_events(root)
    for index, event in enumerate(events, start=1):
        call = tool_call(event)
        if not call:
            continue
        status = str(call.get("normalized_status") or normalize_status(str(call.get("status") or ""), str(call.get("summary") or ""), event.get("data")))
        if status not in KNOWN_STATUSES:
            findings.append(f"event {index} unknown normalized_status: {status}")
        sidecar = call.get("sidecar_path")
        if sidecar and not (root / str(sidecar)).is_file():
            findings.append(f"event {index} sidecar missing: {sidecar}")
        duration = call.get("duration_ms")
        if duration is not None and (not isinstance(duration, (int, float)) or duration < 0):
            findings.append(f"event {index} duration_ms must be a non-negative number or null")
    return findings, payload


def output(value: Any, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        if isinstance(value, dict) and "tools" in value:
            print("Tool Health")
            for item in value["tools"]:
                print(
                    f"- {item['tool']}: calls={item['calls']} "
                    f"success_rate={item['success_rate']} failure_rate={item['failure_rate']} "
                    f"empty={item['empty']} sidecars={item['sidecars']}"
                )
            if not value["tools"]:
                print("no tool events.")
        else:
            print(json.dumps(value, ensure_ascii=False))


def cmd_summary(root: Path, args: argparse.Namespace) -> int:
    output(build_summary(root), args.format)
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    findings, payload = validate(root)
    result = {"ok": not findings, "findings": findings, "tools": payload["tools"]}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif findings:
        print("tool-health findings:")
        for finding in findings:
            print(f"  ERROR {finding}")
    else:
        print(f"tool-health OK: {len(payload['tools'])} tool(s)")
    return 1 if findings else 0


def cmd_normalize_preview(root: Path, args: argparse.Namespace) -> int:
    normalized = normalize_status(args.status, args.summary, None)
    payload = {"status": args.status, "normalized_status": normalized}
    output(payload, args.format)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary").set_defaults(func=cmd_summary)
    sub.add_parser("check").set_defaults(func=cmd_check)
    preview = sub.add_parser("normalize-preview")
    preview.add_argument("--status", required=True)
    preview.add_argument("--summary", default="")
    preview.set_defaults(func=cmd_normalize_preview)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    return args.func(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
