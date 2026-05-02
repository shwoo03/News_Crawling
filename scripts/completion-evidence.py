#!/usr/bin/env python3
"""Manage append-only task completion evidence for agent-run work."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from lib_runtime_lock import runtime_lock
except ImportError:  # pragma: no cover - compatibility for copied script smoke roots
    from contextlib import contextmanager

    @contextmanager
    def runtime_lock(root: Path, name: str, **_: object):
        yield root / "runtime" / "locks" / f"{name}.lock"

try:
    from redact import redact_json, redact_text
except ImportError:  # pragma: no cover - compatibility for copied script smoke roots
    def redact_text(value: str) -> str:
        return value

    def redact_json(value: Any) -> Any:
        return value


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


REQUIRED_FIELDS = ("ts", "goal", "changed_paths", "validations", "outcome")
ALLOWED_OUTCOMES = {"genuine_success", "partial_progress", "timeout", "infra_error", "blocked_by_policy"}
ALLOWED_VALIDATION_STATUSES = {"OK", "PASS", "WARN", "SKIP", "FAIL", "ERROR"}
PASSING_VALIDATION_STATUSES = {"OK", "PASS"}
RISK_VALIDATION_STATUSES = {"WARN", "SKIP"}


@dataclass
class EvidenceRecord:
    ts: str
    goal: str
    changed_paths: list[str]
    validations: list[dict[str, Any]]
    outcome: str
    residual_risk: str = ""
    next_action: str = ""
    notes: str = ""
    agent: str = "codex"
    artifacts: list[str] = field(default_factory=list)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def evidence_path(root: Path) -> Path:
    return root / "runtime" / "completion-evidence.jsonl"


def resolve_under_root(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    resolved.relative_to(root.resolve())
    return resolved


def normalize_path(root: Path, value: str) -> str:
    return resolve_under_root(root, value).relative_to(root.resolve()).as_posix()


def normalize_paths(root: Path, values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        normalized = normalize_path(root, stripped)
        if normalized not in result:
            result.append(normalized)
    return result


def parse_validation(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {"name": value, "command": value, "status": "OK"}
    if not isinstance(payload, dict):
        raise ValueError("--validation JSON must be an object")
    return payload


def validation_status(validation: dict[str, Any]) -> str:
    return str(validation.get("status", "")).strip().upper()


def read_records(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = evidence_path(root)
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


def validate_record(root: Path, record: dict[str, Any], index: int) -> list[str]:
    label = f"record {index}"
    findings: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in record:
            findings.append(f"{label} missing field `{field_name}`")
    if not str(record.get("goal", "")).strip():
        findings.append(f"{label} field `goal` is blank")
    outcome = str(record.get("outcome", ""))
    if outcome and outcome not in ALLOWED_OUTCOMES:
        findings.append(f"{label} field `outcome` invalid: {outcome}")
    changed_paths = record.get("changed_paths")
    if not isinstance(changed_paths, list) or not changed_paths:
        findings.append(f"{label} field `changed_paths` must be a non-empty list")
    else:
        for value in changed_paths:
            if not isinstance(value, str) or not value.strip():
                findings.append(f"{label} has invalid changed path: {value!r}")
                continue
            try:
                normalize_path(root, value)
            except ValueError:
                findings.append(f"{label} changed path outside project root: {value}")
    validations = record.get("validations")
    if not isinstance(validations, list) or not validations:
        findings.append(f"{label} field `validations` must be a non-empty list")
    elif not all(isinstance(item, dict) for item in validations):
        findings.append(f"{label} field `validations` must contain objects")
    else:
        for offset, validation in enumerate(validations, start=1):
            if not str(validation.get("name", "")).strip():
                findings.append(f"{label} validation {offset} missing field `name`")
            status = validation_status(validation)
            if not status:
                findings.append(f"{label} validation {offset} missing field `status`")
            elif status not in ALLOWED_VALIDATION_STATUSES:
                findings.append(f"{label} validation {offset} status invalid: {status}")
        if outcome == "genuine_success":
            failing = [
                validation_status(validation)
                for validation in validations
                if isinstance(validation, dict) and validation_status(validation) not in PASSING_VALIDATION_STATUSES
            ]
            if failing:
                findings.append(f"{label} outcome `genuine_success` requires all validations passing (OK/PASS); got {failing}")
        if outcome == "partial_progress":
            risk_statuses = [
                validation_status(validation)
                for validation in validations
                if isinstance(validation, dict) and validation_status(validation) in RISK_VALIDATION_STATUSES
            ]
            if risk_statuses and not (str(record.get("residual_risk", "")).strip() or str(record.get("next_action", "")).strip()):
                findings.append(f"{label} outcome `partial_progress` with WARN/SKIP requires residual_risk or next_action")
    return findings


def validate_ledger(root: Path) -> tuple[list[str], int]:
    records, findings = read_records(root)
    for index, record in enumerate(records, start=1):
        findings.extend(validate_record(root, record, index))
    return findings, len(records)


def append_record(root: Path, record: EvidenceRecord) -> None:
    path = evidence_path(root)
    path.resolve(strict=False).relative_to(root.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(redact_json(asdict(record)), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with runtime_lock(root, "completion-evidence"):
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    try:
        changed_paths = normalize_paths(root, args.changed_path)
        artifacts = normalize_paths(root, args.artifact)
        validations = [parse_validation(item) for item in args.validation]
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"invalid evidence input: {exc}", file=sys.stderr)
        return 2
    record = EvidenceRecord(
        ts=args.ts or utc_now(),
        goal=redact_text(args.goal.strip()),
        changed_paths=changed_paths,
        validations=redact_json(validations),
        outcome=args.outcome,
        residual_risk=redact_text(args.residual_risk.strip()),
        next_action=redact_text(args.next_action.strip()),
        notes=redact_text(args.notes.strip()),
        agent=args.agent.strip() or "codex",
        artifacts=artifacts,
    )
    findings = validate_record(root, asdict(record), 1)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    append_record(root, record)
    if args.json:
        print(json.dumps(asdict(record), ensure_ascii=False, indent=2))
    else:
        print(f"recorded completion evidence: {record.goal}")
    return 0


def cmd_list(root: Path, args: argparse.Namespace) -> int:
    records, findings = read_records(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    visible = records if args.all else records[-args.last :]
    if args.json:
        print(json.dumps(visible, ensure_ascii=False, indent=2))
        return 0
    if not visible:
        print("no completion evidence records.")
        return 0
    start = len(records) - len(visible) + 1
    for offset, record in enumerate(visible):
        print(f"{start + offset}. [{record.get('outcome', '')}] {record.get('goal', '')}")
        print(f"   paths: {', '.join(record.get('changed_paths') or [])}")
        print(f"   validations: {len(record.get('validations') or [])}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    findings, count = validate_ledger(root)
    if findings:
        print("completion evidence findings:")
        for finding in findings:
            print(f"  ERROR {finding}")
        print(f"checked {count} completion evidence record(s), {len(findings)} error(s)")
        return 1
    if count == 0:
        print("completion evidence OK: no records")
    else:
        print(f"completion evidence OK: {count} record(s) checked")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    sub = parser.add_subparsers(dest="command", required=True)

    add_parser = sub.add_parser("add", help="Append one completion evidence record.")
    add_parser.add_argument("--goal", required=True)
    add_parser.add_argument("--changed-path", action="append", default=[], required=True)
    add_parser.add_argument("--validation", action="append", default=[], required=True)
    add_parser.add_argument("--outcome", choices=sorted(ALLOWED_OUTCOMES), default="genuine_success")
    add_parser.add_argument("--residual-risk", default="")
    add_parser.add_argument("--next-action", default="")
    add_parser.add_argument("--notes", default="")
    add_parser.add_argument("--agent", default="codex")
    add_parser.add_argument("--artifact", action="append", default=[])
    add_parser.add_argument("--ts", default="")
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(func=cmd_add)

    list_parser = sub.add_parser("list", help="List completion evidence records.")
    list_parser.add_argument("--last", type=int, default=20)
    list_parser.add_argument("--all", action="store_true")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    check_parser = sub.add_parser("check", help="Validate completion evidence records.")
    check_parser.set_defaults(func=cmd_check)
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
