#!/usr/bin/env python3
"""Write, validate, and summarize the machine-readable session snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


REQUIRED_FIELDS = (
    "schema_version",
    "ts",
    "project",
    "handoff_path",
    "activity_log_last",
    "completion_evidence_last",
    "open_blockers",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def snapshot_path(root: Path) -> Path:
    return root / "runtime" / "session-snapshot.json"


def infer_project(root: Path) -> str:
    profile = root / "docs" / "PROJECT_PROFILE.md"
    if profile.exists():
        for line in profile.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("- `project_name`:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    return value
    return root.name


def last_jsonl_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            last = value
    return last


def open_blockers(root: Path) -> list[str]:
    path = root / "state" / "blockers.md"
    if not path.exists():
        return []
    blockers: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and "현재 없음" not in stripped:
            blockers.append(stripped[2:])
    return blockers


def build_snapshot(root: Path) -> dict[str, Any]:
    handoff = root / "runtime" / "state" / "session-handoff.md"
    activity_last = last_jsonl_record(root / "runtime" / "activity-log.jsonl")
    evidence_last = last_jsonl_record(root / "runtime" / "completion-evidence.jsonl")
    return {
        "schema_version": "ai-architecture.session-snapshot.v1",
        "ts": utc_now(),
        "project": infer_project(root),
        "handoff_path": "runtime/state/session-handoff.md",
        "handoff_exists": handoff.exists(),
        "activity_log_last": activity_last,
        "completion_evidence_last": evidence_last,
        "open_blockers": open_blockers(root),
    }


def validate_snapshot(root: Path, payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in payload:
            findings.append(f"missing field `{field_name}`")
    if payload.get("schema_version") != "ai-architecture.session-snapshot.v1":
        findings.append("field `schema_version` must be ai-architecture.session-snapshot.v1")
    if not str(payload.get("ts") or "").strip():
        findings.append("field `ts` is blank")
    if not isinstance(payload.get("open_blockers"), list):
        findings.append("field `open_blockers` must be a list")
    if payload.get("activity_log_last") is not None and not isinstance(payload.get("activity_log_last"), dict):
        findings.append("field `activity_log_last` must be object or null")
    if payload.get("completion_evidence_last") is not None and not isinstance(payload.get("completion_evidence_last"), dict):
        findings.append("field `completion_evidence_last` must be object or null")
    if payload.get("handoff_path") and not (root / str(payload["handoff_path"])).exists():
        findings.append(f"handoff path missing: {payload['handoff_path']}")
    current_activity = last_jsonl_record(root / "runtime" / "activity-log.jsonl")
    current_evidence = last_jsonl_record(root / "runtime" / "completion-evidence.jsonl")
    if payload.get("activity_log_last") != current_activity:
        findings.append("activity_log_last is stale; run session-snapshot.py write")
    if payload.get("completion_evidence_last") != current_evidence:
        findings.append("completion_evidence_last is stale; run session-snapshot.py write")
    findings.extend(foreign_path_findings(root, payload))
    return findings


WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


def iter_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for item in value.values():
            found.extend(iter_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(iter_strings(item))
    return found


def foreign_path_findings(root: Path, payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    root_resolved = root.resolve(strict=False)
    seen: set[str] = set()
    for value in iter_strings(payload):
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if WINDOWS_ABS_RE.match(candidate):
            findings.append(f"foreign absolute path in snapshot: {candidate}")
            continue
        if not candidate.startswith("/"):
            continue
        path = Path(candidate).resolve(strict=False)
        try:
            path.relative_to(root_resolved)
        except ValueError:
            findings.append(f"absolute path outside repo in snapshot: {candidate}")
    return findings


def read_snapshot(root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = snapshot_path(root)
    if not path.exists():
        return None, [f"{path.relative_to(root).as_posix()} missing"]
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return None, [f"{path.relative_to(root).as_posix()} invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{path.relative_to(root).as_posix()} must contain a JSON object"]
    return value, validate_snapshot(root, value)


def cmd_write(root: Path, args: argparse.Namespace) -> int:
    payload = build_snapshot(root)
    findings = validate_snapshot(root, payload)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    path = snapshot_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"wrote session snapshot: {path.relative_to(root).as_posix()}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    payload, findings = read_snapshot(root)
    if args.format == "json":
        print(json.dumps({"path": snapshot_path(root).as_posix(), "snapshot": payload, "findings": findings}, ensure_ascii=False, indent=2))
    elif findings:
        print("session-snapshot findings:")
        for finding in findings:
            print(f"  ERROR {finding}")
    else:
        print("session-snapshot OK")
    return 1 if findings else 0


def cmd_summary(root: Path, args: argparse.Namespace) -> int:
    payload, findings = read_snapshot(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    assert payload is not None
    summary = {
        "project": payload.get("project"),
        "ts": payload.get("ts"),
        "open_blockers": len(payload.get("open_blockers") or []),
        "has_activity": payload.get("activity_log_last") is not None,
        "has_completion_evidence": payload.get("completion_evidence_last") is not None,
    }
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("Session Snapshot")
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser("write", help="Write runtime/session-snapshot.json.")
    write.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    write.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    write.set_defaults(func=cmd_write)
    check = sub.add_parser("check", help="Validate runtime/session-snapshot.json.")
    check.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    check.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    check.set_defaults(func=cmd_check)
    summary = sub.add_parser("summary", help="Summarize runtime/session-snapshot.json.")
    summary.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    summary.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    summary.set_defaults(func=cmd_summary)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    return args.func(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
