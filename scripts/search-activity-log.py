#!/usr/bin/env python3
"""Filter and print entries from runtime/activity-log.jsonl.

Designed for quick session recall without shelling into jq. Supports ISO-date
ranges, phase/action/project/tool filters, substring match against the summary,
and "last N" trimming. With no filters, prints the latest 20 entries.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_iso(value: str) -> datetime:
    """Accept YYYY-MM-DD or full RFC3339; always return an aware UTC datetime."""
    text = value.strip()
    if len(text) == 10:
        text += "T00:00:00Z"
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid ISO timestamp '{value}': {exc}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def entry_ts(entry: dict[str, Any]) -> datetime | None:
    raw = entry.get("ts")
    if not isinstance(raw, str):
        return None
    try:
        return parse_iso(raw)
    except argparse.ArgumentTypeError:
        return None


def matches(entry: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.phase and entry.get("phase") != args.phase:
        return False
    if args.action and entry.get("action") != args.action:
        return False
    if args.project and entry.get("project") != args.project:
        return False
    if args.tool:
        tool_call = entry.get("tool_call") or {}
        if tool_call.get("tool") != args.tool:
            return False
    if args.contains:
        summary = ""
        tool_call = entry.get("tool_call")
        if isinstance(tool_call, dict):
            summary = str(tool_call.get("summary") or "")
        if args.contains.lower() not in summary.lower():
            return False
    if args.sidecar_contains:
        tool_call = entry.get("tool_call") or {}
        sidecar = tool_call.get("sidecar_path") if isinstance(tool_call, dict) else None
        if not isinstance(sidecar, str) or not sidecar:
            return False
        log_root = repo_root()
        sidecar_path = (log_root / sidecar).resolve(strict=False)
        try:
            sidecar_path.relative_to(log_root.resolve(strict=False))
        except ValueError:
            return False
        try:
            text = sidecar_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if args.sidecar_contains.lower() not in text.lower():
            return False
    if args.since or args.until:
        ts = entry_ts(entry)
        if ts is None:
            return False
        if args.since and ts < args.since:
            return False
        if args.until and ts > args.until:
            return False
    return True


def render_row(entry: dict[str, Any]) -> str:
    ts = entry.get("ts", "")
    phase = entry.get("phase", "")
    action = entry.get("action", "")
    project = entry.get("project", "")
    tool_call = entry.get("tool_call") or {}
    summary = str(tool_call.get("summary") or "")
    summary_short = (summary[:77] + "...") if len(summary) > 80 else summary
    sidecar = f" sidecar={tool_call.get('sidecar_path')}" if tool_call.get("sidecar_path") else ""
    return f"{ts:20}  {phase:14}  {action:32}  {project:24}  {summary_short}{sidecar}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--log", default=None, help="Path to activity-log.jsonl (default: runtime/activity-log.jsonl).")
    parser.add_argument("--since", type=parse_iso, default=None, help="Only entries at or after this time (ISO-date or RFC3339).")
    parser.add_argument("--until", type=parse_iso, default=None, help="Only entries at or before this time.")
    parser.add_argument("--phase", default=None, help="Exact-match filter on top-level phase field.")
    parser.add_argument("--action", default=None, help="Exact-match filter on action field.")
    parser.add_argument("--project", default=None, help="Exact-match filter on project field.")
    parser.add_argument("--tool", default=None, help="Exact-match filter on tool_call.tool.")
    parser.add_argument("--contains", default=None, help="Case-insensitive substring match against tool_call.summary.")
    parser.add_argument("--sidecar-contains", default=None, help="Case-insensitive substring match against a tool output sidecar.")
    parser.add_argument("--last", type=int, default=None, help="Trim to the last N matches (default 20 when no filter is set).")
    parser.add_argument("--jsonl", action="store_true", help="Emit raw JSONL for matched entries instead of the table.")
    args = parser.parse_args()

    log_path = Path(args.log).resolve() if args.log else repo_root() / "runtime" / "activity-log.jsonl"
    if not log_path.exists():
        print(f"search-activity-log: {log_path} not found", file=sys.stderr)
        return 1

    matched: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(
                    f"search-activity-log: skipping malformed line {line_no}: {exc.msg}",
                    file=sys.stderr,
                )
                continue
            if not isinstance(entry, dict):
                continue
            if matches(entry, args):
                matched.append(entry)

    # Default: last 20 if no filter and no --last specified
    any_filter = any(
        [args.since, args.until, args.phase, args.action, args.project, args.tool, args.contains, args.sidecar_contains]
    )
    limit = args.last if args.last is not None else (None if any_filter else 20)
    if limit is not None and limit > 0:
        matched = matched[-limit:]

    if args.jsonl:
        for entry in matched:
            sys.stdout.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    else:
        header = f"{'ts':20}  {'phase':14}  {'action':32}  {'project':24}  summary"
        print(header)
        print("-" * len(header))
        for entry in matched:
            print(render_row(entry))
        print(f"\n{len(matched)} entr{'y' if len(matched) == 1 else 'ies'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
