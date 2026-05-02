#!/usr/bin/env python3
"""Manage human review items that an agent should not decide alone.

The queue is stored as append-only JSONL events at runtime/review-queue.jsonl.
Commands reconstruct the current state from events, so decisions remain
auditable while ordinary list/add/resolve flows stay simple.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


ALLOWED_TYPES = {
    "contradiction",
    "duplicate",
    "missing-page",
    "confirm",
    "suggestion",
    "risky-update",
    "reference-adoption",
    "skill-lifecycle",
    "notion-duplicate",
}
RESOLVED_STATUSES = {"resolved", "dismissed"}
NON_BLOCKING_STATUSES = {"resolved", "dismissed", "deferred"}


@dataclass
class ReviewItem:
    id: str
    type: str
    title: str
    description: str
    status: str
    created_at: str
    updated_at: str
    source_path: str = ""
    affected_paths: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    decision: str = ""
    note: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def queue_path(root: Path) -> Path:
    return root / "runtime" / "review-queue.jsonl"


def normalize_title(title: str) -> str:
    text = title.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9가-힣 _./:-]+", "", text)
    return text


def item_key(item_type: str, title: str) -> str:
    return f"{item_type}::{normalize_title(title)}"


def ensure_inside_root(path: Path, root: Path) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve() if path.exists() else path
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise SystemExit(f"queue path must be inside project root {resolved_root}; got {resolved_path}")


def read_events(root: Path) -> list[dict[str, Any]]:
    path = queue_path(root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no} invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise SystemExit(f"{path}:{line_no} JSONL event must be an object")
        events.append(value)
    return events


def append_event(root: Path, event: dict[str, Any]) -> None:
    path = queue_path(root)
    ensure_inside_root(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    result: list[str] = []
    for value in [*existing, *incoming]:
        stripped = value.strip()
        if stripped and stripped not in result:
            result.append(stripped)
    return result


def reconstruct(events: list[dict[str, Any]]) -> dict[str, ReviewItem]:
    items: dict[str, ReviewItem] = {}
    for event in events:
        action = event.get("action")
        item_id = str(event.get("id", ""))
        ts = str(event.get("ts", ""))
        if not item_id:
            continue
        if action == "add":
            items[item_id] = ReviewItem(
                id=item_id,
                type=str(event.get("type", "")),
                title=str(event.get("title", "")),
                description=str(event.get("description", "")),
                status="open",
                created_at=ts,
                updated_at=ts,
                source_path=str(event.get("source_path", "")),
                affected_paths=list(event.get("affected_paths") or []),
                search_queries=list(event.get("search_queries") or []),
                options=list(event.get("options") or []),
            )
            continue
        item = items.get(item_id)
        if not item:
            continue
        item.updated_at = ts or item.updated_at
        if action == "merge":
            item.description = str(event.get("description") or item.description)
            item.source_path = str(event.get("source_path") or item.source_path)
            item.affected_paths = merge_unique(item.affected_paths, list(event.get("affected_paths") or []))
            item.search_queries = merge_unique(item.search_queries, list(event.get("search_queries") or []))
            item.options = merge_unique(item.options, list(event.get("options") or []))
        elif action == "resolve":
            item.status = "resolved"
            item.decision = str(event.get("decision", ""))
            item.note = str(event.get("note", ""))
        elif action == "defer":
            item.status = "deferred"
            item.decision = "deferred"
            item.note = str(event.get("note", ""))
        elif action == "dismiss":
            item.status = "dismissed"
            item.note = str(event.get("note", ""))
    return items


def find_open_duplicate(items: dict[str, ReviewItem], item_type: str, title: str) -> ReviewItem | None:
    key = item_key(item_type, title)
    for item in items.values():
        if item.status not in NON_BLOCKING_STATUSES and item_key(item.type, item.title) == key:
            return item
    return None


def new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"review-{stamp}-{uuid.uuid4().hex[:8]}"


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    events = read_events(root)
    items = reconstruct(events)
    duplicate = find_open_duplicate(items, args.type, args.title)
    now = utc_now()
    if duplicate:
        event = {
            "ts": now,
            "action": "merge",
            "id": duplicate.id,
            "description": args.description,
            "source_path": args.source_path,
            "affected_paths": args.affected_path,
            "search_queries": args.search_query,
            "options": args.option,
        }
        append_event(root, event)
        message = f"merged existing review item: {duplicate.id}"
        output = {"status": "merged", "id": duplicate.id}
    else:
        item_id = new_id()
        event = {
            "ts": now,
            "action": "add",
            "id": item_id,
            "type": args.type,
            "title": args.title,
            "description": args.description,
            "source_path": args.source_path,
            "affected_paths": args.affected_path,
            "search_queries": args.search_query,
            "options": args.option,
        }
        append_event(root, event)
        message = f"added review item: {item_id}"
        output = {"status": "added", "id": item_id}
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(message)
    return 0


def visible_items(items: dict[str, ReviewItem], args: argparse.Namespace) -> list[ReviewItem]:
    result = list(items.values())
    if not args.all:
        result = [item for item in result if item.status not in RESOLVED_STATUSES]
    if args.type:
        result = [item for item in result if item.type == args.type]
    return sorted(result, key=lambda item: (item.status in RESOLVED_STATUSES, item.created_at, item.id))


def cmd_list(root: Path, args: argparse.Namespace) -> int:
    items = visible_items(reconstruct(read_events(root)), args)
    if args.json:
        print(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2))
        return 0
    if not items:
        print("no review items.")
        return 0
    for item in items:
        print(f"{item.id} [{item.status}] {item.type}: {item.title}")
        if item.description:
            print(f"  desc: {item.description}")
        if item.affected_paths:
            print(f"  affected: {', '.join(item.affected_paths)}")
        if item.search_queries:
            print(f"  queries: {', '.join(item.search_queries)}")
        if item.options:
            print(f"  options: {', '.join(item.options)}")
        if item.decision:
            print(f"  decision: {item.decision}")
        if item.note:
            print(f"  note: {item.note}")
    return 0


def cmd_show(root: Path, args: argparse.Namespace) -> int:
    items = reconstruct(read_events(root))
    item = items.get(args.id)
    if not item:
        print(f"review item not found: {args.id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(asdict(item), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(asdict(item), ensure_ascii=False, indent=2))
    return 0


def cmd_resolve(root: Path, args: argparse.Namespace) -> int:
    items = reconstruct(read_events(root))
    item = items.get(args.id)
    if not item:
        print(f"review item not found: {args.id}", file=sys.stderr)
        return 1
    if item.status in RESOLVED_STATUSES:
        print(f"review item already {item.status}: {args.id}", file=sys.stderr)
        return 1
    append_event(
        root,
        {
            "ts": utc_now(),
            "action": "resolve",
            "id": args.id,
            "decision": args.decision,
            "note": args.note,
        },
    )
    print(f"resolved review item: {args.id}")
    return 0


def cmd_dismiss(root: Path, args: argparse.Namespace) -> int:
    items = reconstruct(read_events(root))
    item = items.get(args.id)
    if not item:
        print(f"review item not found: {args.id}", file=sys.stderr)
        return 1
    if item.status in RESOLVED_STATUSES:
        print(f"review item already {item.status}: {args.id}", file=sys.stderr)
        return 1
    append_event(
        root,
        {
            "ts": utc_now(),
            "action": "dismiss",
            "id": args.id,
            "note": args.note,
        },
    )
    print(f"dismissed review item: {args.id}")
    return 0


def cmd_defer(root: Path, args: argparse.Namespace) -> int:
    items = reconstruct(read_events(root))
    item = items.get(args.id)
    if not item:
        print(f"review item not found: {args.id}", file=sys.stderr)
        return 1
    if item.status in RESOLVED_STATUSES:
        print(f"review item already {item.status}: {args.id}", file=sys.stderr)
        return 1
    if item.status == "deferred":
        print(f"review item already deferred: {args.id}", file=sys.stderr)
        return 1
    append_event(
        root,
        {
            "ts": utc_now(),
            "action": "defer",
            "id": args.id,
            "decision": "deferred",
            "note": args.note,
        },
    )
    print(f"deferred review item: {args.id}")
    return 0


def cmd_count(root: Path, args: argparse.Namespace) -> int:
    items = reconstruct(read_events(root))
    open_items = [item for item in items.values() if item.status == "open"]
    if args.json:
        counts = {
            "open": len(open_items),
            "resolved": sum(1 for item in items.values() if item.status == "resolved"),
            "dismissed": sum(1 for item in items.values() if item.status == "dismissed"),
            "deferred": sum(1 for item in items.values() if item.status == "deferred"),
            "total": len(items),
        }
        print(json.dumps(counts, ensure_ascii=False, indent=2))
    else:
        print(len(open_items))
    return 1 if args.strict and open_items else 0


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _proposal_decision(root: Path, source_path: str) -> str:
    if not source_path.endswith(".md"):
        return ""
    path = root / source_path
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- `decision`:"):
            decision = stripped.split(":", 1)[1].strip()
            return decision if decision in {"accepted", "rejected", "deferred"} else ""
    return ""


def build_sweep_actions(root: Path, items: dict[str, ReviewItem], stale_days: int) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    open_items = [item for item in items.values() if item.status == "open"]
    seen_keys: dict[str, ReviewItem] = {}
    now = datetime.now(timezone.utc)
    for item in sorted(open_items, key=lambda value: (value.created_at, value.id)):
        key = item_key(item.type, item.title)
        if key in seen_keys:
            actions.append({
                "id": item.id,
                "action": "dismiss",
                "reason": f"duplicate of open review item {seen_keys[key].id}",
                "decision": "",
            })
            continue
        seen_keys[key] = item

        if item.source_path:
            source = root / item.source_path
            if not source.exists():
                actions.append({
                    "id": item.id,
                    "action": "dismiss",
                    "reason": f"source_path missing: {item.source_path}",
                    "decision": "",
                })
                continue
            decision = _proposal_decision(root, item.source_path)
            if decision:
                actions.append({
                    "id": item.id,
                    "action": "resolve" if decision in {"accepted", "rejected"} else "defer",
                    "reason": f"proposal already has decision: {decision}",
                    "decision": decision,
                })
                continue

        created = _parse_iso(item.created_at)
        if stale_days >= 0 and created and (now - created).days >= stale_days:
            actions.append({
                "id": item.id,
                "action": "dismiss",
                "reason": f"open item is stale for >= {stale_days} day(s)",
                "decision": "",
            })
    return actions


def cmd_sweep(root: Path, args: argparse.Namespace) -> int:
    items = reconstruct(read_events(root))
    actions = build_sweep_actions(root, items, args.stale_days)
    applied: list[dict[str, str]] = []
    if args.apply:
        for action in actions:
            event = {
                "ts": utc_now(),
                "action": action["action"],
                "id": action["id"],
                "note": f"sweep: {action['reason']}",
            }
            if action["action"] == "resolve":
                event["decision"] = action["decision"] or "resolved_by_sweep"
            if action["action"] == "defer":
                event["decision"] = "deferred"
            append_event(root, event)
            applied.append(action)
    payload = {
        "status": "applied" if args.apply else "dry_run",
        "stale_days": args.stale_days,
        "actions": actions,
        "applied": applied,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not actions:
            print("review queue sweep: no stale items")
        else:
            for action in actions:
                prefix = "APPLY" if args.apply else "DRY-RUN"
                print(f"{prefix} {action['action']} {action['id']}: {action['reason']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    sub = parser.add_subparsers(dest="command", required=True)

    add_parser = sub.add_parser("add", help="Add or merge a pending review item.")
    add_parser.add_argument("--type", required=True, choices=sorted(ALLOWED_TYPES))
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--source-path", default="")
    add_parser.add_argument("--affected-path", action="append", default=[])
    add_parser.add_argument("--search-query", action="append", default=[])
    add_parser.add_argument("--option", action="append", default=[])
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(func=cmd_add)

    list_parser = sub.add_parser("list", help="List review items.")
    list_parser.add_argument("--all", action="store_true", help="Include resolved and dismissed items.")
    list_parser.add_argument("--type", choices=sorted(ALLOWED_TYPES), default=None)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    show_parser = sub.add_parser("show", help="Show one review item.")
    show_parser.add_argument("id")
    show_parser.add_argument("--json", action="store_true")
    show_parser.set_defaults(func=cmd_show)

    resolve_parser = sub.add_parser("resolve", help="Resolve one review item with a decision.")
    resolve_parser.add_argument("id")
    resolve_parser.add_argument("--decision", required=True)
    resolve_parser.add_argument("--note", default="")
    resolve_parser.set_defaults(func=cmd_resolve)

    dismiss_parser = sub.add_parser("dismiss", help="Dismiss one review item without a decision.")
    dismiss_parser.add_argument("id")
    dismiss_parser.add_argument("--note", default="")
    dismiss_parser.set_defaults(func=cmd_dismiss)

    defer_parser = sub.add_parser("defer", help="Mark one review item as deferred without hiding it as dismissed.")
    defer_parser.add_argument("id")
    defer_parser.add_argument("--note", default="")
    defer_parser.set_defaults(func=cmd_defer)

    count_parser = sub.add_parser("count", help="Print the number of unresolved review items.")
    count_parser.add_argument("--strict", action="store_true", help="Exit 1 when unresolved items exist.")
    count_parser.add_argument("--json", action="store_true")
    count_parser.set_defaults(func=cmd_count)

    sweep_parser = sub.add_parser("sweep", help="Find stale or already-decided review items.")
    sweep_parser.add_argument("--dry-run", action="store_true", help="Preview sweep actions without writing events.")
    sweep_parser.add_argument("--apply", action="store_true", help="Append resolve/dismiss events for proposed sweep actions.")
    sweep_parser.add_argument("--stale-days", type=int, default=30)
    sweep_parser.add_argument("--json", action="store_true")
    sweep_parser.set_defaults(func=cmd_sweep)

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
