#!/usr/bin/env python3
"""Build and query a local SQLite FTS recall index from append-only state."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SOURCES = (
    ("runtime/activity-log.jsonl", "activity"),
    ("runtime/completion-evidence.jsonl", "completion"),
    ("runtime/skill-usage.jsonl", "skill_usage"),
    ("state/decisions.md", "decision"),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def db_path(root: Path) -> Path:
    return root / "runtime" / "session-recall.sqlite"


def iter_jsonl(path: Path, source_type: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    records: list[dict[str, str]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload: Any = json.loads(line)
        except json.JSONDecodeError:
            payload = {"raw": line}
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if isinstance(payload, (dict, list)) else str(payload)
        records.append({"source": path.as_posix(), "source_type": source_type, "ref": str(line_no), "text": text})
    return records


def iter_markdown_decisions(path: Path, source_type: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks: list[dict[str, str]] = []
    current_ref = "1"
    current: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            if current:
                chunks.append({"source": path.as_posix(), "source_type": source_type, "ref": current_ref, "text": "\n".join(current)})
            current_ref = str(line_no)
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append({"source": path.as_posix(), "source_type": source_type, "ref": current_ref, "text": "\n".join(current)})
    return chunks


def collect_records(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for rel, source_type in SOURCES:
        path = root / rel
        if path.suffix == ".jsonl":
            records.extend(iter_jsonl(path, source_type))
        else:
            records.extend(iter_markdown_decisions(path, source_type))
    return records


def source_state(root: Path) -> list[dict[str, Any]]:
    state: list[dict[str, Any]] = []
    for rel, source_type in SOURCES:
        path = root / rel
        if not path.exists():
            state.append({"source": rel, "source_type": source_type, "exists": False, "mtime_ns": 0, "size": 0, "record_count": 0})
            continue
        stat = path.stat()
        if path.suffix == ".jsonl":
            record_count = len(iter_jsonl(path, source_type))
        else:
            record_count = len(iter_markdown_decisions(path, source_type))
        state.append(
            {
                "source": rel,
                "source_type": source_type,
                "exists": True,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "record_count": record_count,
            }
        )
    return state


def connect(root: Path) -> sqlite3.Connection:
    path = db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS recall USING fts5(source, source_type, ref, text)")
    conn.execute("CREATE TABLE IF NOT EXISTS recall_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return conn


def rebuild_index(root: Path) -> int:
    records = collect_records(root)
    conn = connect(root)
    with conn:
        conn.execute("DELETE FROM recall")
        conn.executemany(
            "INSERT INTO recall(source, source_type, ref, text) VALUES(?,?,?,?)",
            [(record["source"], record["source_type"], record["ref"], record["text"]) for record in records],
        )
        conn.execute(
            "INSERT OR REPLACE INTO recall_meta(key, value) VALUES(?, ?)",
            ("source_state", json.dumps(source_state(root), ensure_ascii=False, sort_keys=True)),
        )
    return len(records)


def indexed_source_state(conn: sqlite3.Connection) -> list[dict[str, Any]] | None:
    try:
        row = conn.execute("SELECT value FROM recall_meta WHERE key = ?", ("source_state",)).fetchone()
    except sqlite3.DatabaseError:
        return None
    if not row:
        return None
    try:
        value = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, list) else None


def stale_sources(root: Path, conn: sqlite3.Connection) -> list[str]:
    indexed = indexed_source_state(conn)
    if indexed is None:
        return [rel for rel, _ in SOURCES]
    current_by_source = {item["source"]: item for item in source_state(root)}
    stale: list[str] = []
    for item in indexed:
        if not isinstance(item, dict):
            return [rel for rel, _ in SOURCES]
        source = str(item.get("source", ""))
        current = current_by_source.get(source)
        if current is None or current != item:
            stale.append(source or "(unknown)")
    for source in current_by_source:
        if source not in {str(item.get("source", "")) for item in indexed if isinstance(item, dict)}:
            stale.append(source)
    return sorted(set(stale))


def cmd_index(root: Path, args: argparse.Namespace) -> int:
    count = rebuild_index(root)
    payload = {"indexed": count, "database": db_path(root).relative_to(root).as_posix()}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"session recall indexed {count} record(s)")
    return 0


def cmd_search(root: Path, args: argparse.Namespace) -> int:
    if not db_path(root).exists():
        rebuild_index(root)
    conn = connect(root)
    if stale_sources(root, conn):
        rebuild_index(root)
        conn = connect(root)
    query = args.query.strip()
    if not query:
        print("query is required", file=sys.stderr)
        return 2
    rows = conn.execute(
        "SELECT source, source_type, ref, snippet(recall, 3, '[', ']', '...', 12) FROM recall WHERE recall MATCH ? LIMIT ?",
        (query, args.limit),
    ).fetchall()
    payload = [
        {"source": row[0], "source_type": row[1], "ref": row[2], "snippet": row[3]}
        for row in rows
    ]
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not payload:
            print("no session recall matches.")
        for item in payload:
            print(f"{item['source']}:{item['ref']} [{item['source_type']}] {item['snippet']}")
    return 0


def cmd_summary(root: Path, args: argparse.Namespace) -> int:
    if not db_path(root).exists():
        rebuild_index(root)
    conn = connect(root)
    rows = conn.execute("SELECT source_type, count(*) FROM recall GROUP BY source_type ORDER BY source_type").fetchall()
    payload = {"database": db_path(root).relative_to(root).as_posix(), "counts": {row[0]: row[1] for row in rows}}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("session recall summary:")
        for key, count in payload["counts"].items():
            print(f"  {key}: {count}")
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    if not db_path(root).exists():
        if args.format == "json":
            print(json.dumps({"ok": True, "count": 0, "database": db_path(root).relative_to(root).as_posix(), "status": "not_indexed"}, ensure_ascii=False, indent=2))
        else:
            print("session recall OK: not indexed yet")
        return 0
    try:
        conn = connect(root)
        count = conn.execute("SELECT count(*) FROM recall").fetchone()[0]
        stale = stale_sources(root, conn)
    except sqlite3.DatabaseError as exc:
        if args.format == "json":
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"session recall invalid: {exc}")
        return 1
    if stale:
        payload = {"ok": False, "count": count, "database": db_path(root).relative_to(root).as_posix(), "status": "stale", "stale_sources": stale}
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("session recall stale: " + ", ".join(stale))
            print("run `python scripts/session-recall.py index` to refresh")
        return 1
    if args.format == "json":
        print(json.dumps({"ok": True, "count": count, "database": db_path(root).relative_to(root).as_posix(), "status": "current"}, ensure_ascii=False, indent=2))
    else:
        print(f"session recall OK: {count} indexed record(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("index", cmd_index), ("summary", cmd_summary), ("check", cmd_check)):
        item = sub.add_parser(name)
        item.add_argument("--format", choices=("text", "json"), default="text")
        item.set_defaults(func=func)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--format", choices=("text", "json"), default="text")
    search.set_defaults(func=cmd_search)
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
