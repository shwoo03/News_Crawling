#!/usr/bin/env python3
"""Manage append-only named checkpoints for long agent tasks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


ALLOWED_VERIFY_STATUS = {"not_run", "passed", "failed", "partial"}


@dataclass
class Checkpoint:
    id: str
    ts: str
    name: str
    goal: str
    git_sha: str
    changed_paths: list[str]
    verify_status: str
    note: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def checkpoint_path(root: Path) -> Path:
    return root / "runtime" / "checkpoints.jsonl"


def git_sha(root: Path) -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def normalize_paths(root: Path, values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values or ["."]:
        path = Path(value)
        resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
        try:
            rel = resolved.relative_to(root.resolve(strict=False)).as_posix()
        except ValueError as exc:
            raise ValueError(f"changed path outside root: {value}") from exc
        if rel not in result:
            result.append(rel)
    return result


def read_records(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = checkpoint_path(root)
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    findings: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} invalid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} record must be an object")
            continue
        records.append(record)
    return records, findings


def validate_record(record: dict[str, Any], index: int) -> list[str]:
    findings: list[str] = []
    for field in ("id", "ts", "name", "goal", "git_sha", "changed_paths", "verify_status"):
        if field not in record:
            findings.append(f"record {index} missing field `{field}`")
    if record.get("verify_status") not in ALLOWED_VERIFY_STATUS:
        findings.append(f"record {index} invalid verify_status: {record.get('verify_status')}")
    if not isinstance(record.get("changed_paths"), list) or not record.get("changed_paths"):
        findings.append(f"record {index} changed_paths must be a non-empty list")
    return findings


def cmd_create(root: Path, args: argparse.Namespace) -> int:
    try:
        changed_paths = normalize_paths(root, args.changed_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    record = Checkpoint(
        id=args.id or f"checkpoint-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
        ts=utc_now(),
        name=args.name,
        goal=args.goal,
        git_sha=git_sha(root),
        changed_paths=changed_paths,
        verify_status=args.verify_status,
        note=args.note,
    )
    findings = validate_record(asdict(record), 1)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    path = checkpoint_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    if args.format == "json":
        print(json.dumps(asdict(record), ensure_ascii=False, indent=2))
    else:
        print(f"checkpoint created: {record.id} [{record.verify_status}] {record.name}")
    return 0


def cmd_list(root: Path, args: argparse.Namespace) -> int:
    records, findings = read_records(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    visible = records[-args.last :] if args.last else records
    if args.format == "json":
        print(json.dumps(visible, ensure_ascii=False, indent=2))
    else:
        if not visible:
            print("no checkpoints.")
        for record in visible:
            print(f"{record.get('id')} [{record.get('verify_status')}] {record.get('name')} - {record.get('goal')}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    records, findings = read_records(root)
    for index, record in enumerate(records, start=1):
        findings.extend(validate_record(record, index))
    if args.format == "json":
        print(json.dumps({"ok": not findings, "count": len(records), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        if findings:
            print("checkpoint findings:")
            for finding in findings:
                print(f"  ERROR {finding}")
        else:
            print(f"checkpoint ledger OK: {len(records)} record(s)")
    return 1 if findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--goal", required=True)
    create.add_argument("--changed-path", action="append", default=[])
    create.add_argument("--verify-status", choices=sorted(ALLOWED_VERIFY_STATUS), default="not_run")
    create.add_argument("--note", default="")
    create.add_argument("--id", default="")
    create.add_argument("--format", choices=("text", "json"), default="text")
    create.set_defaults(func=cmd_create)
    list_parser = sub.add_parser("list")
    list_parser.add_argument("--last", type=int, default=20)
    list_parser.add_argument("--format", choices=("text", "json"), default="text")
    list_parser.set_defaults(func=cmd_list)
    check = sub.add_parser("check")
    check.add_argument("--format", choices=("text", "json"), default="text")
    check.set_defaults(func=cmd_check)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    return args.func(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
