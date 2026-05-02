#!/usr/bin/env python3
"""Manage the append-only install/convert state ledger."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


REQUIRED_FIELDS = (
    "ts",
    "event",
    "project",
    "skeleton_version",
    "source_commit",
    "requested_profile",
    "selected_components",
    "generated_paths",
    "preserved_paths",
    "validation_status",
)
VALIDATION_STATUSES = {"unverified", "verified", "failed"}


@dataclass
class InstallStateRecord:
    ts: str
    event: str
    project: str
    skeleton_version: str | None
    source_commit: str | None
    requested_profile: str = "full-canonical"
    selected_components: list[str] = field(default_factory=lambda: ["canonical"])
    generated_paths: list[str] = field(default_factory=list)
    preserved_paths: list[str] = field(default_factory=list)
    validation_status: str = "unverified"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ledger_path(root: Path) -> Path:
    return root / "runtime" / "install-state.jsonl"


def read_text_or_none(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except subprocess.SubprocessError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def infer_project(root: Path) -> str:
    profile = root / "docs" / "PROJECT_PROFILE.md"
    if profile.exists():
        for line in profile.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("- `project_name`:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    return value
    return root.name


def append_record(root: Path, record: InstallStateRecord) -> None:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def read_records(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = ledger_path(root)
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    findings: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} JSONL record must be an object")
            continue
        records.append(value)
    return records, findings


def validate_record(record: dict[str, Any], index: int) -> list[str]:
    label = f"record {index}"
    findings: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in record:
            findings.append(f"{label} missing field `{field_name}`")
    for field_name in ("ts", "event", "project", "requested_profile", "validation_status"):
        if field_name in record and not str(record.get(field_name) or "").strip():
            findings.append(f"{label} field `{field_name}` is blank")
    if "validation_status" in record and record.get("validation_status") not in VALIDATION_STATUSES:
        findings.append(
            f"{label} field `validation_status` must be one of: "
            + ", ".join(sorted(VALIDATION_STATUSES))
        )
    for field_name in ("selected_components", "generated_paths", "preserved_paths"):
        value = record.get(field_name)
        if field_name in record and not isinstance(value, list):
            findings.append(f"{label} field `{field_name}` must be a list")
        elif isinstance(value, list) and not all(isinstance(item, str) for item in value):
            findings.append(f"{label} field `{field_name}` must contain strings")
    for field_name in ("skeleton_version", "source_commit"):
        if field_name in record and record.get(field_name) is not None and not isinstance(record.get(field_name), str):
            findings.append(f"{label} field `{field_name}` must be string or null")
    return findings


def validate_ledger(root: Path) -> tuple[list[str], int, list[dict[str, Any]]]:
    records, findings = read_records(root)
    for index, record in enumerate(records, start=1):
        findings.extend(validate_record(record, index))
    return findings, len(records), records


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    record = InstallStateRecord(
        ts=args.ts or utc_now(),
        event=args.event,
        project=args.project or infer_project(root),
        skeleton_version=args.skeleton_version if args.skeleton_version else read_text_or_none(root / ".skeleton-version"),
        source_commit=args.source_commit if args.source_commit else git_commit(root),
        requested_profile=args.requested_profile,
        selected_components=args.selected_component or ["canonical"],
        generated_paths=args.generated_path or [],
        preserved_paths=args.preserved_path or [],
        validation_status=args.validation_status,
    )
    findings = validate_record(asdict(record), 1)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    append_record(root, record)
    if args.format == "json":
        print(json.dumps(asdict(record), ensure_ascii=False, indent=2))
    else:
        print(f"recorded install state: {record.event}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    findings, count, records = validate_ledger(root)
    warnings: list[str] = []
    if records:
        latest = records[-1]
        if latest.get("validation_status") == "unverified":
            warnings.append(
                "latest install-state event is unverified; append a verified or failed event after validation"
            )
    if args.format == "json":
        print(
            json.dumps(
                {
                    "path": ledger_path(root).as_posix(),
                    "records": count,
                    "findings": findings,
                    "warnings": warnings,
                    "latest_validation_status": records[-1].get("validation_status") if records else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif findings or warnings:
        print("install-state findings:")
        for finding in findings:
            print(f"  ERROR {finding}")
        for warning in warnings:
            print(f"  WARN {warning}")
        print(f"checked {count} install-state record(s), {len(findings)} error(s), {len(warnings)} warning(s)")
    else:
        print(f"install-state OK: {count} record(s) checked" if count else "install-state OK: no records")
    return 1 if findings or (args.strict and warnings) else 0


def cmd_summary(root: Path, args: argparse.Namespace) -> int:
    records, findings = read_records(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    last = records[-1] if records else None
    payload = {
        "path": ledger_path(root).as_posix(),
        "records": len(records),
        "last_event": last.get("event") if last else None,
        "last_validation_status": last.get("validation_status") if last else None,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Install State")
        print(f"records: {payload['records']}")
        print(f"last_event: {payload['last_event'] or 'n/a'}")
        print(f"last_validation_status: {payload['last_validation_status'] or 'n/a'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Append one install-state event.")
    add.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    add.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    add.add_argument("--event", default="convert_completed")
    add.add_argument("--project", default="")
    add.add_argument("--skeleton-version", default="")
    add.add_argument("--source-commit", default="")
    add.add_argument("--requested-profile", default="full-canonical")
    add.add_argument("--selected-component", action="append", default=[])
    add.add_argument("--generated-path", action="append", default=[])
    add.add_argument("--preserved-path", action="append", default=[])
    add.add_argument("--validation-status", default="unverified")
    add.add_argument("--ts", default="")
    add.set_defaults(func=cmd_add)

    check = sub.add_parser("check", help="Validate install-state ledger.")
    check.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    check.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    check.add_argument("--strict", action="store_true", help="Fail when the latest event is unverified.")
    check.set_defaults(func=cmd_check)

    summary = sub.add_parser("summary", help="Summarize install-state ledger.")
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
