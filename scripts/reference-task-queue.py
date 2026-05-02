#!/usr/bin/env python3
"""Manage append-only reference analysis tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
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
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


TERMINAL_STATUSES = {"done", "failed", "cancelled"}
ALLOWED_STATUSES = {"queued", "running", *TERMINAL_STATUSES}
ALLOWED_ACTIONS = {"add", "claim", "complete", "fail", "cancel", "retry"}


@dataclass
class ReferenceTask:
    id: str
    status: str
    target: str
    goal: str
    created_at: str
    updated_at: str
    candidate_card: str = ""
    proposal: str = ""
    claimed_by: str = ""
    error: str = ""
    note: str = ""
    source_hash: str = ""
    hash_algorithm: str = ""
    retry_count: int = 0
    max_retries: int = 2
    last_run_status: str = ""
    skip_reason: str = ""


HASH_SKIP_DIRS = {".git", "node_modules", "dist", "build", ".cache", "__pycache__"}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def queue_path(root: Path) -> Path:
    return root / "runtime" / "reference-tasks.jsonl"


def new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"ref-task-{stamp}-{uuid.uuid4().hex[:8]}"


def rel_or_value(root: Path, value: str) -> str:
    if not value:
        return ""
    path = Path(value)
    resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    try:
        return resolved.relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return value


def target_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)


def hash_target(root: Path, value: str) -> tuple[str, str]:
    path = target_path(root, value)
    if not path.exists():
        return "", ""
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.name.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        return digest.hexdigest(), "sha256"
    if not path.is_dir():
        return "", ""
    for item in sorted(path.rglob("*")):
        rel_parts = item.relative_to(path).parts
        if any(part in HASH_SKIP_DIRS for part in rel_parts):
            continue
        if item.is_dir():
            continue
        rel = item.relative_to(path).as_posix()
        digest.update(b"path\0")
        digest.update(rel.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        try:
            digest.update(item.read_bytes())
        except OSError:
            continue
        digest.update(b"\0")
    return digest.hexdigest(), "sha256"


def read_events(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = queue_path(root)
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    findings: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} invalid JSON: {exc}")
            continue
        if not isinstance(event, dict):
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} event must be an object")
            continue
        events.append(event)
    return events, findings


def read_events_or_exit(root: Path) -> list[dict[str, Any]]:
    events, findings = read_events(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        raise SystemExit(1)
    return events


def append_event(root: Path, event: dict[str, Any]) -> None:
    path = queue_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with runtime_lock(root, "reference-tasks"):
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def reconstruct(events: list[dict[str, Any]]) -> dict[str, ReferenceTask]:
    tasks: dict[str, ReferenceTask] = {}
    for event in events:
        action = str(event.get("action", ""))
        task_id = str(event.get("id", ""))
        ts = str(event.get("ts", "")) or utc_now()
        if not task_id:
            continue
        if action == "add":
            tasks[task_id] = ReferenceTask(
                id=task_id,
                status="queued",
                target=str(event.get("target", "")),
                goal=str(event.get("goal", "")),
                created_at=ts,
                updated_at=ts,
                candidate_card=str(event.get("candidate_card", "")),
                proposal=str(event.get("proposal", "")),
                note=str(event.get("note", "")),
                source_hash=str(event.get("source_hash", "")),
                hash_algorithm=str(event.get("hash_algorithm", "")),
                retry_count=int(event.get("retry_count", 0) or 0),
                max_retries=int(event.get("max_retries", 2) or 2),
                last_run_status=str(event.get("last_run_status", "")),
                skip_reason=str(event.get("skip_reason", "")),
            )
            continue
        task = tasks.get(task_id)
        if not task:
            continue
        task.updated_at = ts
        if action == "claim":
            task.status = "running"
            task.claimed_by = str(event.get("claimed_by", ""))
            task.last_run_status = "running"
        elif action == "complete":
            task.status = "done"
            task.candidate_card = str(event.get("candidate_card") or task.candidate_card)
            task.proposal = str(event.get("proposal") or task.proposal)
            task.note = str(event.get("note", ""))
            task.last_run_status = "done"
        elif action == "fail":
            task.status = "failed"
            task.error = str(event.get("error", ""))
            task.last_run_status = "failed"
            task.retry_count = int(event.get("retry_count", task.retry_count) or task.retry_count)
        elif action == "cancel":
            task.status = "cancelled"
            task.note = str(event.get("note", ""))
            task.last_run_status = "cancelled"
        elif action == "retry":
            task.status = "queued"
            task.retry_count = int(event.get("retry_count", task.retry_count + 1) or task.retry_count + 1)
            task.last_run_status = "retry"
            task.error = ""
    return tasks


def duplicate_add_ids(events: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for event in events:
        if str(event.get("action", "")) != "add":
            continue
        task_id = str(event.get("id", ""))
        if not task_id:
            continue
        if task_id in seen and task_id not in duplicates:
            duplicates.append(task_id)
        seen.add(task_id)
    return duplicates


def validate_event_sequence(events: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    states: dict[str, str] = {}
    retry_counts: dict[str, int] = {}
    max_retries: dict[str, int] = {}
    for index, event in enumerate(events, start=1):
        action = str(event.get("action", ""))
        task_id = str(event.get("id", ""))
        label = f"event {index}"
        if action not in ALLOWED_ACTIONS:
            findings.append(f"{label} unknown action: {action or '<missing>'}")
            continue
        if not task_id:
            findings.append(f"{label} missing id")
            continue
        current = states.get(task_id)
        if action == "add":
            if current is not None:
                findings.append(f"{label} duplicate add after task already exists: {task_id}")
            if not str(event.get("target", "")).strip():
                findings.append(f"{label} add missing target")
            states[task_id] = "queued"
            retry_counts[task_id] = int(event.get("retry_count", 0) or 0)
            max_retries[task_id] = int(event.get("max_retries", 2) or 2)
            continue
        if current is None:
            findings.append(f"{label} {action} references unknown task: {task_id}")
            continue
        if current in TERMINAL_STATUSES and action != "retry":
            findings.append(f"{label} {action} after terminal status {current}: {task_id}")
            continue
        if action == "claim":
            if current != "queued":
                findings.append(f"{label} invalid transition {current} -> running: {task_id}")
            states[task_id] = "running"
        elif action == "complete":
            if current not in {"queued", "running"}:
                findings.append(f"{label} invalid transition {current} -> done: {task_id}")
            states[task_id] = "done"
        elif action == "fail":
            if current not in {"queued", "running"}:
                findings.append(f"{label} invalid transition {current} -> failed: {task_id}")
            states[task_id] = "failed"
        elif action == "cancel":
            if current not in {"queued", "running"}:
                findings.append(f"{label} invalid transition {current} -> cancelled: {task_id}")
            states[task_id] = "cancelled"
        elif action == "retry":
            if current != "failed":
                findings.append(f"{label} invalid transition {current} -> queued by retry: {task_id}")
            next_retry = int(event.get("retry_count", retry_counts.get(task_id, 0) + 1) or 0)
            if next_retry > max_retries.get(task_id, 2):
                findings.append(f"{label} retry_count exceeds max_retries for {task_id}")
            retry_counts[task_id] = next_retry
            states[task_id] = "queued"
    return findings


def task_or_error(tasks: dict[str, ReferenceTask], task_id: str) -> ReferenceTask:
    task = tasks.get(task_id)
    if not task:
        raise SystemExit(f"reference task not found: {task_id}")
    return task


def output(value: Any, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        if isinstance(value, list):
            if not value:
                print("no reference tasks.")
            for item in value:
                print(f"{item['id']} [{item['status']}] {item['target']} - {item.get('goal', '')}")
        elif isinstance(value, dict):
            print(json.dumps(value, ensure_ascii=False))


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    events = read_events_or_exit(root)
    task_id = args.id or new_id()
    if task_id in reconstruct(events):
        print(f"reference task id already exists: {task_id}", file=sys.stderr)
        return 1
    source_hash = args.source_hash
    hash_algorithm = "sha256" if source_hash else ""
    if not source_hash:
        source_hash, hash_algorithm = hash_target(root, args.target)
    normalized_target = rel_or_value(root, args.target)
    if source_hash:
        for task in reconstruct(events).values():
            if task.target == normalized_target and task.source_hash == source_hash and task.status in {"queued", "running", "done"}:
                payload = {
                    "id": task.id,
                    "status": task.status,
                    "target": task.target,
                    "source_hash": source_hash,
                    "hash_algorithm": hash_algorithm,
                    "skipped": True,
                    "skip_reason": "unchanged",
                }
                output(payload, args.format)
                return 0
    event = {
        "ts": utc_now(),
        "action": "add",
        "id": task_id,
        "target": normalized_target,
        "goal": args.goal,
        "candidate_card": rel_or_value(root, args.candidate_card),
        "proposal": rel_or_value(root, args.proposal),
        "note": args.note,
        "source_hash": source_hash,
        "hash_algorithm": hash_algorithm,
        "retry_count": 0,
        "max_retries": args.max_retries,
        "last_run_status": "queued",
        "skip_reason": "",
    }
    append_event(root, event)
    payload = {"id": task_id, "status": "queued", "target": event["target"], "source_hash": source_hash, "hash_algorithm": hash_algorithm}
    output(payload, args.format)
    return 0


def cmd_list(root: Path, args: argparse.Namespace) -> int:
    events, findings = read_events(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    tasks = list(reconstruct(events).values())
    if args.status:
        tasks = [task for task in tasks if task.status == args.status]
    output([asdict(task) for task in sorted(tasks, key=lambda item: (item.created_at, item.id))], args.format)
    return 0


def cmd_claim(root: Path, args: argparse.Namespace) -> int:
    tasks = reconstruct(read_events_or_exit(root))
    task = task_or_error(tasks, args.id)
    if task.status != "queued":
        print(f"reference task is not queued: {args.id} ({task.status})", file=sys.stderr)
        return 1
    append_event(root, {"ts": utc_now(), "action": "claim", "id": args.id, "claimed_by": args.by})
    output({"id": args.id, "status": "running", "claimed_by": args.by}, args.format)
    return 0


def cmd_complete(root: Path, args: argparse.Namespace) -> int:
    tasks = reconstruct(read_events_or_exit(root))
    task = task_or_error(tasks, args.id)
    if task.status in TERMINAL_STATUSES:
        print(f"reference task already terminal: {args.id} ({task.status})", file=sys.stderr)
        return 1
    append_event(
        root,
        {
            "ts": utc_now(),
            "action": "complete",
            "id": args.id,
            "candidate_card": rel_or_value(root, args.candidate_card),
            "proposal": rel_or_value(root, args.proposal),
            "note": args.note,
        },
    )
    output({"id": args.id, "status": "done"}, args.format)
    return 0


def cmd_fail(root: Path, args: argparse.Namespace) -> int:
    tasks = reconstruct(read_events_or_exit(root))
    task = task_or_error(tasks, args.id)
    if task.status in TERMINAL_STATUSES:
        print(f"reference task already terminal: {args.id} ({task.status})", file=sys.stderr)
        return 1
    append_event(root, {"ts": utc_now(), "action": "fail", "id": args.id, "error": args.error, "retry_count": task.retry_count})
    output({"id": args.id, "status": "failed", "retry_count": task.retry_count}, args.format)
    return 0


def cmd_retry(root: Path, args: argparse.Namespace) -> int:
    tasks = reconstruct(read_events_or_exit(root))
    task = task_or_error(tasks, args.id)
    if task.status != "failed":
        print(f"reference task is not failed: {args.id} ({task.status})", file=sys.stderr)
        return 1
    next_retry = task.retry_count + 1
    if next_retry > task.max_retries:
        print(f"reference task exceeded max retries: {args.id} ({task.max_retries})", file=sys.stderr)
        return 1
    append_event(root, {"ts": utc_now(), "action": "retry", "id": args.id, "retry_count": next_retry, "note": args.note})
    output({"id": args.id, "status": "queued", "retry_count": next_retry, "max_retries": task.max_retries}, args.format)
    return 0


def cmd_cancel(root: Path, args: argparse.Namespace) -> int:
    tasks = reconstruct(read_events_or_exit(root))
    task = task_or_error(tasks, args.id)
    if task.status in TERMINAL_STATUSES:
        print(f"reference task already terminal: {args.id} ({task.status})", file=sys.stderr)
        return 1
    append_event(root, {"ts": utc_now(), "action": "cancel", "id": args.id, "note": args.note})
    output({"id": args.id, "status": "cancelled"}, args.format)
    return 0


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    events, findings = read_events(root)
    findings.extend(validate_event_sequence(events))
    for task_id in duplicate_add_ids(events):
        findings.append(f"{task_id} duplicate add event")
    tasks = reconstruct(events)
    for task in tasks.values():
        if task.status not in ALLOWED_STATUSES:
            findings.append(f"{task.id} invalid status: {task.status}")
        if not task.target:
            findings.append(f"{task.id} missing target")
        if task.hash_algorithm and task.hash_algorithm != "sha256":
            findings.append(f"{task.id} unsupported hash_algorithm: {task.hash_algorithm}")
        if task.retry_count < 0:
            findings.append(f"{task.id} retry_count must be non-negative")
        if task.max_retries < 0:
            findings.append(f"{task.id} max_retries must be non-negative")
        if task.candidate_card and not (root / task.candidate_card).exists():
            findings.append(f"{task.id} candidate_card missing: {task.candidate_card}")
        if task.proposal and not (root / task.proposal).exists():
            findings.append(f"{task.id} proposal missing: {task.proposal}")
    if findings:
        if args.format == "json":
            print(json.dumps({"ok": False, "findings": findings, "count": len(tasks)}, ensure_ascii=False, indent=2))
        else:
            print("reference task findings:")
            for finding in findings:
                print(f"  ERROR {finding}")
        return 1
    if args.format == "json":
        print(json.dumps({"ok": True, "findings": [], "count": len(tasks)}, ensure_ascii=False, indent=2))
    else:
        print(f"reference task queue OK: {len(tasks)} task(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("--target", required=True)
    add.add_argument("--goal", default="reference analysis")
    add.add_argument("--candidate-card", default="")
    add.add_argument("--proposal", default="")
    add.add_argument("--note", default="")
    add.add_argument("--id", default="")
    add.add_argument("--source-hash", default="")
    add.add_argument("--max-retries", type=int, default=2)
    add.add_argument("--format", choices=("text", "json"), default="text")
    add.set_defaults(func=cmd_add)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), default="")
    list_parser.add_argument("--format", choices=("text", "json"), default="text")
    list_parser.set_defaults(func=cmd_list)

    claim = sub.add_parser("claim")
    claim.add_argument("id")
    claim.add_argument("--by", default="codex")
    claim.add_argument("--format", choices=("text", "json"), default="text")
    claim.set_defaults(func=cmd_claim)

    complete = sub.add_parser("complete")
    complete.add_argument("id")
    complete.add_argument("--candidate-card", default="")
    complete.add_argument("--proposal", default="")
    complete.add_argument("--note", default="")
    complete.add_argument("--format", choices=("text", "json"), default="text")
    complete.set_defaults(func=cmd_complete)

    fail = sub.add_parser("fail")
    fail.add_argument("id")
    fail.add_argument("--error", required=True)
    fail.add_argument("--format", choices=("text", "json"), default="text")
    fail.set_defaults(func=cmd_fail)

    retry = sub.add_parser("retry")
    retry.add_argument("id")
    retry.add_argument("--note", default="")
    retry.add_argument("--format", choices=("text", "json"), default="text")
    retry.set_defaults(func=cmd_retry)

    cancel = sub.add_parser("cancel")
    cancel.add_argument("id")
    cancel.add_argument("--note", default="")
    cancel.add_argument("--format", choices=("text", "json"), default="text")
    cancel.set_defaults(func=cmd_cancel)

    check = sub.add_parser("check")
    check.add_argument("--format", choices=("text", "json"), default="text")
    check.set_defaults(func=cmd_check)
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
