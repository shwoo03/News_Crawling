#!/usr/bin/env python3
"""Manage and validate the append-only cost ledger."""

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
    "run_id",
    "agent",
    "skill",
    "provider",
    "model",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "cost_usd",
    "cost_status",
    "cost_source",
)
ALLOWED_COST_STATUS = {"actual", "estimated", "unknown", "not_applicable"}


@dataclass
class CostRecord:
    ts: str
    run_id: str
    agent: str
    skill: str
    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_status: str
    cost_source: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ledger_path(root: Path) -> Path:
    return root / "state" / "cost-log.jsonl"


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
    for field_name in ("ts", "run_id", "agent", "provider", "model", "cost_status", "cost_source"):
        if field_name in record and not str(record.get(field_name) or "").strip():
            findings.append(f"{label} field `{field_name}` is blank")
    if record.get("cost_status") and record.get("cost_status") not in ALLOWED_COST_STATUS:
        findings.append(f"{label} field `cost_status` invalid: {record.get('cost_status')}")
    for field_name in ("input_tokens", "cached_input_tokens", "output_tokens"):
        value = record.get(field_name)
        if field_name in record and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            findings.append(f"{label} field `{field_name}` must be a non-negative integer")
    cost = record.get("cost_usd")
    if "cost_usd" in record and (not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0):
        findings.append(f"{label} field `cost_usd` must be a non-negative number")
    return findings


def validate_ledger(root: Path) -> tuple[list[str], int]:
    records, findings = read_records(root)
    for index, record in enumerate(records, start=1):
        findings.extend(validate_record(record, index))
    return findings, len(records)


def append_record(root: Path, record: CostRecord) -> None:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    record = CostRecord(
        ts=args.ts or utc_now(),
        run_id=args.run_id,
        agent=args.agent,
        skill=args.skill,
        provider=args.provider,
        model=args.model,
        input_tokens=args.input_tokens,
        cached_input_tokens=args.cached_input_tokens,
        output_tokens=args.output_tokens,
        cost_usd=args.cost_usd,
        cost_status=args.cost_status,
        cost_source=args.cost_source,
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
        print(f"recorded cost event: {record.run_id}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    findings, count = validate_ledger(root)
    if args.format == "json":
        print(json.dumps({"path": ledger_path(root).as_posix(), "records": count, "findings": findings}, ensure_ascii=False, indent=2))
    elif findings:
        print("cost-log findings:")
        for finding in findings:
            print(f"  ERROR {finding}")
        print(f"checked {count} cost record(s), {len(findings)} error(s)")
    else:
        print(f"cost-log OK: {count} record(s) checked" if count else "cost-log OK: no records")
    return 1 if findings else 0


def cmd_summary(root: Path, args: argparse.Namespace) -> int:
    records, findings = read_records(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    total = sum(float(record.get("cost_usd") or 0) for record in records)
    tokens = sum(int(record.get("input_tokens") or 0) + int(record.get("output_tokens") or 0) for record in records)
    payload = {"records": len(records), "total_cost_usd": round(total, 6), "total_tokens": tokens}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Cost Log")
        print(f"records: {payload['records']}")
        print(f"total_cost_usd: {payload['total_cost_usd']}")
        print(f"total_tokens: {payload['total_tokens']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Append one cost event.")
    add.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    add.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    add.add_argument("--run-id", required=True)
    add.add_argument("--agent", required=True)
    add.add_argument("--skill", default="")
    add.add_argument("--provider", required=True)
    add.add_argument("--model", required=True)
    add.add_argument("--input-tokens", type=int, default=0)
    add.add_argument("--cached-input-tokens", type=int, default=0)
    add.add_argument("--output-tokens", type=int, default=0)
    add.add_argument("--cost-usd", type=float, default=0.0)
    add.add_argument("--cost-status", choices=sorted(ALLOWED_COST_STATUS), default="unknown")
    add.add_argument("--cost-source", default="manual")
    add.add_argument("--ts", default="")
    add.set_defaults(func=cmd_add)

    check = sub.add_parser("check", help="Validate cost ledger.")
    check.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    check.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    check.set_defaults(func=cmd_check)

    summary = sub.add_parser("summary", help="Summarize cost ledger.")
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
