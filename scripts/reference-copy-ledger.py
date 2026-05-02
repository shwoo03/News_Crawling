#!/usr/bin/env python3
"""Record copied open-source code provenance in an append-only JSONL ledger."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
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
    "source_url",
    "license",
    "revision",
    "source_path",
    "local_path",
    "copy_boundary",
    "redistribution_review_required",
)


@dataclass
class LedgerRecord:
    ts: str
    source_url: str
    license: str
    revision: str
    source_path: str
    copied_symbol: str
    local_path: str
    copy_boundary: str
    redistribution_review_required: bool
    candidate_card: str = ""
    proposal: str = ""
    notes: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ledger_path(root: Path) -> Path:
    return root / "runtime" / "reference-copy-ledger.jsonl"


def is_blank(value: Any) -> bool:
    return not str(value).strip()


def resolve_under_root(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    resolved.relative_to(root.resolve())
    return resolved


def normalize_repo_path(root: Path, value: str) -> str:
    return resolve_under_root(root, value).relative_to(root.resolve()).as_posix()


def normalize_optional_path(root: Path, value: str) -> str:
    return normalize_repo_path(root, value) if value.strip() else ""


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


def validate_record(root: Path, record: dict[str, Any], index: int) -> list[str]:
    label = f"record {index}"
    findings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            findings.append(f"{label} missing field `{field}`")
        elif field == "redistribution_review_required":
            if not isinstance(record[field], bool):
                findings.append(f"{label} field `redistribution_review_required` must be boolean")
        elif is_blank(record[field]):
            findings.append(f"{label} field `{field}` is blank")

    for field in ("local_path", "candidate_card", "proposal"):
        value = str(record.get(field, "")).strip()
        if not value:
            continue
        try:
            normalized = normalize_repo_path(root, value)
        except ValueError:
            findings.append(f"{label} field `{field}` points outside project root: {value}")
            continue
        if value != normalized and Path(value).is_absolute():
            findings.append(f"{label} field `{field}` must be stored as repo-relative path: {value}")
        if field in {"candidate_card", "proposal"} and not (root / normalized).is_file():
            findings.append(f"{label} field `{field}` target does not exist: {normalized}")
    return findings


def validate_ledger(root: Path) -> tuple[list[str], int]:
    records, findings = read_records(root)
    for index, record in enumerate(records, start=1):
        findings.extend(validate_record(root, record, index))
    return findings, len(records)


def append_record(root: Path, record: LedgerRecord) -> None:
    path = ledger_path(root)
    resolved_path = path.resolve(strict=False)
    resolved_path.relative_to(root.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    try:
        local_path = normalize_repo_path(root, args.local_path)
        candidate_card = normalize_optional_path(root, args.candidate_card)
        proposal = normalize_optional_path(root, args.proposal)
    except ValueError as exc:
        print(f"path must stay inside project root {root}: {exc}", file=sys.stderr)
        return 2

    record = LedgerRecord(
        ts=args.ts or utc_now(),
        source_url=args.source_url.strip(),
        license=args.license.strip(),
        revision=args.revision.strip(),
        source_path=args.source_path.strip(),
        copied_symbol=args.copied_symbol.strip() or "not specified",
        local_path=local_path,
        copy_boundary=args.copy_boundary.strip(),
        redistribution_review_required=args.redistribution_review_required,
        candidate_card=candidate_card,
        proposal=proposal,
        notes=args.notes.strip(),
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
        print(f"recorded copied source: {record.local_path}")
    return 0


def cmd_list(root: Path, args: argparse.Namespace) -> int:
    records, findings = read_records(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0
    if not records:
        print("no copied-source ledger entries.")
        return 0
    for index, record in enumerate(records, start=1):
        print(
            f"{index}. {record.get('local_path', '')} "
            f"<- {record.get('source_url', '')}@{record.get('revision', '')}"
        )
        print(f"   license: {record.get('license', '')}")
        print(f"   boundary: {record.get('copy_boundary', '')}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    findings, count = validate_ledger(root)
    if findings:
        print("copied-source ledger findings:")
        for finding in findings:
            print(f"  ERROR {finding}")
        print(f"checked {count} copied-source record(s), {len(findings)} error(s)")
        return 1
    if count == 0:
        print("copied-source ledger OK: no copied-source records")
    else:
        print(f"copied-source ledger OK: {count} record(s) checked")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    sub = parser.add_subparsers(dest="command", required=True)

    add_parser = sub.add_parser("add", help="Append one copied-source record.")
    add_parser.add_argument("--source-url", required=True)
    add_parser.add_argument("--license", required=True)
    add_parser.add_argument("--revision", required=True)
    add_parser.add_argument("--source-path", required=True)
    add_parser.add_argument("--copied-symbol", default="not specified")
    add_parser.add_argument("--local-path", required=True)
    add_parser.add_argument("--copy-boundary", required=True)
    add_parser.add_argument(
        "--redistribution-review-required",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether redistribution requires a fresh license review.",
    )
    add_parser.add_argument("--candidate-card", default="")
    add_parser.add_argument("--proposal", default="")
    add_parser.add_argument("--notes", default="")
    add_parser.add_argument("--ts", default="")
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(func=cmd_add)

    list_parser = sub.add_parser("list", help="List copied-source records.")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    check_parser = sub.add_parser("check", help="Validate the copied-source ledger.")
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
