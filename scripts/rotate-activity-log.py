#!/usr/bin/env python3
"""Rotate append-only JSONL runtime logs into monthly archives.

Per `docs/RUNTIME_EVENT_SCHEMA.md` "로그 크기 관리 정책", when
`runtime/activity-log.jsonl` or `runtime/agent-runs.jsonl` exceeds 10,000
lines the older entries should be split into
`runtime/archive/<base>-YYYY-MM.jsonl` and the original file should retain
only the most recent month. This script implements that policy.

Defaults to dry-run; pass `--apply` to actually move lines. After a
successful `--apply` rotation, appends a `{"action": "log_archived", ...}`
event to `runtime/activity-log.jsonl` so the rotation itself is auditable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Cross-platform advisory file locking. Matches the locking strategy in
# scripts/hooks/post-tool-use-log.py so a concurrent hook append and a
# rotation cannot interleave partial writes.
try:
    import fcntl  # type: ignore[import-not-found]

    def _lock_exclusive(handle: Any) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _unlock(handle: Any) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
except ImportError:  # Windows
    import msvcrt  # type: ignore[import-not-found]
    import time

    def _lock_exclusive(handle: Any) -> None:
        # msvcrt.locking(LK_LOCK,...) retries for ~10 seconds then raises.
        # Wrap in our own loop so long rotations (>10s) still serialize
        # cleanly instead of racing. Lock 1 byte at offset 0; seek there
        # first so we're not locking past EOF on an empty file.
        handle.seek(0)
        deadline = time.monotonic() + 60.0
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)

    def _unlock(handle: Any) -> None:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


# Recognize the ts prefix "YYYY-MM" so we can bucket without a full parse.
# The schema says ts is ISO-8601 UTC ("YYYY-MM-DDTHH:MM:SSZ"); entries missing
# a parseable ts are bucketed into "unknown" and stay with the oldest archive
# bucket rather than being dropped.
_TS_MONTH_RE = re.compile(r'"ts"\s*:\s*"(\d{4})-(\d{2})-')

DEFAULT_THRESHOLD = 10_000
LOG_BASES = ("activity-log", "agent-runs")


@dataclass
class RotationPlan:
    base: str
    source: Path
    total_lines: int
    keep_month: str | None  # "YYYY-MM" of the newest month to retain in source
    buckets: dict[str, list[str]]  # YYYY-MM -> lines to append to archive
    retained: list[str]  # lines to keep in the original file


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _month_of(line: str) -> str | None:
    match = _TS_MONTH_RE.search(line)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}"


def _read_lines(path: Path) -> list[str]:
    # utf-8-sig transparently strips a BOM if present so the first line parses
    # the same way downstream consumers (verify-skeleton, post-tool-use-log)
    # read it.
    text = path.read_text(encoding="utf-8-sig")
    # Keep only non-empty lines; preserve trailing newline handling by
    # re-adding one on write.
    return [line for line in text.splitlines() if line.strip()]


def plan_rotation(path: Path, threshold: int) -> RotationPlan | None:
    base = path.stem  # "activity-log" / "agent-runs"
    if not path.exists():
        return None
    lines = _read_lines(path)
    if len(lines) <= threshold:
        return RotationPlan(
            base=base,
            source=path,
            total_lines=len(lines),
            keep_month=None,
            buckets={},
            retained=lines,
        )

    months: list[str | None] = [_month_of(line) for line in lines]
    # Newest month is the month of the LAST line with a parseable ts. Using
    # the last line respects the schema note that file-order is authoritative
    # rather than ts sort order.
    keep_month: str | None = None
    for month in reversed(months):
        if month is not None:
            keep_month = month
            break

    buckets: dict[str, list[str]] = {}
    retained: list[str] = []
    for line, month in zip(lines, months):
        if keep_month is not None and month == keep_month:
            retained.append(line)
        else:
            # Lines without a parseable month bucket under the oldest known
            # month in this file, or "unknown" if no line has a parseable ts.
            target = month
            if target is None:
                # Fall back to the earliest parseable month; if none exist,
                # "unknown" keeps them grouped rather than dropping silently.
                target = next((m for m in months if m is not None), "unknown")
            buckets.setdefault(target, []).append(line)

    return RotationPlan(
        base=base,
        source=path,
        total_lines=len(lines),
        keep_month=keep_month,
        buckets=buckets,
        retained=retained,
    )


def _ensure_within(root: Path, path: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise SystemExit(f"refusing to write outside project root: {path}")


def apply_rotation(
    root: Path, plan: RotationPlan, archive_dir: Path
) -> tuple[int, list[Path]]:
    """Write archives and rewrite the source. Returns (lines_moved, archives)."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    _ensure_within(root, archive_dir)

    touched_archives: list[Path] = []
    lines_moved = 0

    # Append to each monthly archive first. Only after all archives are on disk
    # do we rewrite the source. That ordering means a crash mid-rotation leaves
    # a duplicate (archive + source) rather than a data loss.
    for month, bucket_lines in sorted(plan.buckets.items()):
        archive_path = archive_dir / f"{plan.base}-{month}.jsonl"
        _ensure_within(root, archive_path)
        with archive_path.open("a", encoding="utf-8", newline="\n") as handle:
            _lock_exclusive(handle)
            try:
                handle.seek(0, os.SEEK_END)
                for line in bucket_lines:
                    handle.write(line + "\n")
                handle.flush()
            finally:
                _unlock(handle)
        touched_archives.append(archive_path)
        lines_moved += len(bucket_lines)

    # Atomic replace of the source: write retained lines to a temp file in the
    # same directory, then os.replace() over the original. os.replace is atomic
    # on both POSIX and Windows when source and dest share a filesystem.
    src = plan.source
    _ensure_within(root, src)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{plan.base}.", suffix=".jsonl.tmp", dir=src.parent
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as handle:
            for line in plan.retained:
                handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, src)
    except Exception:
        # Clean up temp if replace failed. If replace succeeded the temp no
        # longer exists and unlink will fail silently.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return lines_moved, touched_archives


def append_archive_event(
    activity_log: Path, base: str, archives: list[Path], lines_moved: int
) -> None:
    """Record the rotation in the activity log (schema: action=log_archived)."""
    event = {
        "ts": utc_now(),
        "phase": "maintenance",
        "action": "log_archived",
        "project": "unknown",
        "goal_lineage": [],
        "tool_call": {
            "tool": "scripts/rotate-activity-log.py",
            "status": "completed",
            "summary": f"rotated {base}: moved {lines_moved} line(s) to archive",
        },
        "data": {
            "base": base,
            "lines_moved": lines_moved,
            "archives": [p.name for p in archives],
        },
    }
    activity_log.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    with activity_log.open("a", encoding="utf-8", newline="\n") as handle:
        _lock_exclusive(handle)
        try:
            handle.seek(0, os.SEEK_END)
            handle.write(line + "\n")
            handle.flush()
        finally:
            _unlock(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=None,
        help="Project root (defaults to this script's repo root).",
    )
    parser.add_argument(
        "--threshold", type=int, default=DEFAULT_THRESHOLD,
        help=f"Rotate when a log has more than this many lines (default: {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually rotate. Without this flag, prints a dry-run plan.",
    )
    parser.add_argument(
        "--base", action="append", choices=list(LOG_BASES), default=None,
        help="Rotate only a specific base (repeatable). Default: both.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2

    bases = args.base or list(LOG_BASES)
    runtime = root / "runtime"
    archive_dir = runtime / "archive"

    any_rotated = False
    for base in bases:
        src = runtime / f"{base}.jsonl"
        if not src.exists():
            print(f"{base}: {src.relative_to(root).as_posix()} does not exist; skipping")
            continue

        if args.apply:
            # Serialize concurrent rotations via a sidecar lockfile that
            # survives os.replace() of the source. Holding this across the
            # entire read-plan-apply cycle prevents the TOCTOU where two
            # processes compute the same plan and both move lines to the
            # archive (causing duplicate entries). The hook-side append path
            # still locks the source directly; this rotation lock only
            # serializes rotations against each other. Brief concurrent
            # appends during rotation are acceptable because apply_rotation
            # re-reads the source after acquiring the lock.
            runtime.mkdir(parents=True, exist_ok=True)
            lock_path = runtime / f".{base}.rotation.lock"
            with lock_path.open("a+", encoding="utf-8") as lock_handle:
                _lock_exclusive(lock_handle)
                try:
                    plan = plan_rotation(src, args.threshold)
                    if plan is None or not plan.buckets:
                        if plan is not None:
                            print(
                                f"{base}: {plan.total_lines} line(s) <= threshold "
                                f"{args.threshold}; no rotation needed"
                            )
                        continue
                    summary = ", ".join(
                        f"{month}={len(lines)}"
                        for month, lines in sorted(plan.buckets.items())
                    )
                    keep = plan.keep_month or "unknown"
                    total_move = sum(len(v) for v in plan.buckets.values())
                    print(
                        f"{base}: {plan.total_lines} line(s); would move {total_move} to archive "
                        f"({summary}); keep {len(plan.retained)} line(s) from {keep}"
                    )
                    moved, archives = apply_rotation(root, plan, archive_dir)
                    rel_archives = [a.relative_to(root).as_posix() for a in archives]
                    print(f"  applied: moved {moved} line(s) -> {', '.join(rel_archives)}")
                    append_archive_event(
                        runtime / "activity-log.jsonl", base, archives, moved
                    )
                    any_rotated = True
                finally:
                    _unlock(lock_handle)
        else:
            plan = plan_rotation(src, args.threshold)
            if plan is None or not plan.buckets:
                if plan is not None:
                    print(
                        f"{base}: {plan.total_lines} line(s) <= threshold "
                        f"{args.threshold}; no rotation needed"
                    )
                continue
            summary = ", ".join(
                f"{month}={len(lines)}"
                for month, lines in sorted(plan.buckets.items())
            )
            keep = plan.keep_month or "unknown"
            total_move = sum(len(v) for v in plan.buckets.values())
            print(
                f"{base}: {plan.total_lines} line(s); would move {total_move} to archive "
                f"({summary}); keep {len(plan.retained)} line(s) from {keep}"
            )

    if not args.apply:
        print("(dry-run; pass --apply to perform the rotation)")
    elif not any_rotated:
        print("nothing to rotate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
