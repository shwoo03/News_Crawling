#!/usr/bin/env python3
"""Append a normalized post-tool-use event to runtime/activity-log.jsonl."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from redact import redact_json, redact_text

# Cross-platform advisory file locking. Concurrent post-tool-use hooks (e.g.
# parallel tool calls) could otherwise interleave partial writes into the
# append-only JSONL log, producing corrupt lines. fcntl on POSIX, msvcrt on
# Windows; both acquire an exclusive lock on the open file handle.
try:
    import fcntl  # type: ignore[import-not-found]

    def _lock_exclusive(handle: Any) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _unlock(handle: Any) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
except ImportError:  # Windows
    import msvcrt  # type: ignore[import-not-found]

    def _lock_exclusive(handle: Any) -> None:
        # Lock a single byte at current position; Windows file locks are
        # mandatory but byte-range, so any overlapping locker will block.
        # Use LK_LOCK (blocking) with a retry-until-acquired 1-byte region.
        handle.seek(0, os.SEEK_END)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            # LK_LOCK retries ~10 times then raises. Fall back to best-effort:
            # proceed without a lock rather than drop the event entirely.
            pass

    def _unlock(handle: Any) -> None:
        try:
            handle.seek(0, os.SEEK_END)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_stdin_json() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    # Read raw bytes and decode with utf-8-sig so a leading BOM (common from
    # Windows tools) is stripped transparently. Reading through sys.stdin.read()
    # relies on the current stdin encoding which may not be utf-8 on Windows,
    # leaving the BOM character in the stream and breaking json.loads.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8-sig").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("stdin JSON must be an object")
    return value


def parse_goal_lineage(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(">") if part.strip()]


def normalize_status(status: str, summary: str, payload: dict[str, Any]) -> tuple[str, str, bool]:
    raw = (status or "").strip().lower()
    summary_text = (summary or "").strip()
    if raw in {"ok", "success", "succeeded", "completed", "pass", "passed"}:
        normalized = "success"
    elif raw in {"fail", "failed", "failure", "error", "errored"}:
        normalized = "failure"
    elif raw in {"timeout", "timed_out", "timed-out"}:
        normalized = "timeout"
    elif raw in {"skip", "skipped"}:
        normalized = "skipped"
    else:
        normalized = "unknown"
    empty_output = not summary_text and not payload.get("data")
    if empty_output and normalized == "success":
        normalized = "empty"
    failure_type = ""
    if normalized in {"failure", "timeout"}:
        failure_type = normalized
    elif normalized == "unknown":
        failure_type = "unknown_status"
    return normalized, failure_type, empty_output


def sidecar_for_summary(root: Path, summary: str, max_chars: int) -> tuple[str, dict[str, Any]]:
    summary = redact_text(summary)
    if len(summary) <= max_chars:
        return summary, {}
    directory = root / "runtime" / "tool-output-sidecars"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{utc_now().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}.txt"
    path = directory / name
    path.write_text(summary, encoding="utf-8")
    preview = summary[: max_chars - 3].rstrip() + "..."
    return preview, {
        "sidecar_path": path.relative_to(root).as_posix(),
        "preview_chars": len(preview),
        "full_chars": len(summary),
        "truncated": True,
    }


def _warn_if_ts_regression(log_path: Path, new_ts: str) -> None:
    """Emit a non-fatal warning when the new entry's ts is earlier than the
    last entry's ts in the same file. Per docs/RUNTIME_EVENT_SCHEMA.md, line
    order (not ts) is authoritative, so this is advisory only.
    """
    if not log_path.exists():
        return
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, 2)  # end
            size = handle.tell()
            if size == 0:
                return
            # Read up to last 4 KB to find the last newline-terminated line.
            window = min(size, 4096)
            handle.seek(size - window)
            chunk = handle.read().decode("utf-8", errors="replace")
        stripped_lines = [line for line in chunk.splitlines() if line.strip()]
        if not stripped_lines:
            return
        last_line = stripped_lines[-1]
        try:
            last_entry = json.loads(last_line)
        except json.JSONDecodeError:
            return
        last_ts = last_entry.get("ts")
        if isinstance(last_ts, str) and new_ts < last_ts:
            print(
                f"post-tool-use-log warning: new ts {new_ts} is earlier than "
                f"last entry ts {last_ts}. Line order remains authoritative "
                f"per RUNTIME_EVENT_SCHEMA.md.",
                file=sys.stderr,
            )
    except OSError:
        # Non-fatal: the warning is best-effort.
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--summary", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--phase", default="implementation")
    parser.add_argument("--action", default="post_tool_use")
    parser.add_argument("--goal-lineage", default=None, help="Use 'task > project > primary goal'.")
    parser.add_argument("--log", default=None, help="Override log path.")
    parser.add_argument("--max-summary-chars", type=int, default=2000)
    args = parser.parse_args()

    try:
        payload = read_stdin_json()
        tool = args.tool or payload.get("tool") or payload.get("tool_name") or "unknown"
        status = args.status or payload.get("status") or "completed"
        payload = redact_json(payload)
        summary = args.summary or payload.get("summary") or payload.get("message") or ""
        project = args.project or payload.get("project") or "unknown"
        # Accept goal_lineage from CLI ("a > b > c") or stdin JSON (list or string).
        cli_lineage = parse_goal_lineage(args.goal_lineage)
        payload_lineage = payload.get("goal_lineage")
        if cli_lineage:
            goal_lineage = cli_lineage
        elif isinstance(payload_lineage, list):
            goal_lineage = payload_lineage
        elif isinstance(payload_lineage, str):
            goal_lineage = parse_goal_lineage(payload_lineage)
        elif payload_lineage is None:
            goal_lineage = []
        else:
            raise ValueError(
                "goal_lineage must be a list, an 'a > b > c' string, or absent"
            )

        root = repo_root().resolve()
        # Resolve the default path too, not just the --log override. Otherwise
        # a symlink planted at runtime/activity-log.jsonl would be opened in
        # append mode at the link target (which could lie outside root). With
        # .resolve() in both branches, the subsequent containment check catches
        # that escape before any write happens.
        if args.log:
            log_path = Path(args.log).resolve()
        else:
            default = root / "runtime" / "activity-log.jsonl"
            # Resolve the parent separately so a missing log file (common on a
            # fresh project) does not prevent resolution. The parent must exist
            # and resolve; if the leaf is a symlink, its target is then checked.
            log_path = (default.resolve() if default.exists() else default)
        # Refuse paths outside the project root. Prevents accidental or
        # malicious --log values (e.g. /etc/passwd, ../../secret.log) and
        # symlinked log files from writing the activity stream outside the
        # bounded project tree.
        try:
            log_path.relative_to(root)
        except ValueError:
            raise SystemExit(
                f"--log must be inside the project root {root}; "
                f"got {log_path}"
            )
        log_path.parent.mkdir(parents=True, exist_ok=True)

        summary, sidecar = sidecar_for_summary(root, str(summary), args.max_summary_chars)
        normalized_status, failure_type, empty_output = normalize_status(str(status), str(summary), payload)
        duration_ms = payload.get("duration_ms")
        if not isinstance(duration_ms, (int, float)) or duration_ms < 0:
            duration_ms = None
        event = {
            "ts": utc_now(),
            "phase": args.phase,
            "action": args.action,
            "project": project,
            "goal_lineage": goal_lineage,
            "tool_call": {
                "tool": tool,
                "status": status,
                "normalized_status": normalized_status,
                "failure_type": failure_type,
                "empty_output": empty_output,
                "duration_ms": duration_ms,
                "summary": summary,
                **sidecar,
            },
            # Coerce `data` to a dict even when the payload sets it to null so
            # the emitted event shape stays stable for downstream consumers.
            "data": payload.get("data") if isinstance(payload.get("data"), dict) else {},
        }
        _warn_if_ts_regression(log_path, event["ts"])
        # allow_nan=False refuses to emit non-standard JSON (`NaN`, `Infinity`,
        # `-Infinity`) that could otherwise enter via `payload["data"]` and
        # break strict JSON readers of the log downstream.
        line = json.dumps(
            event, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ) + "\n"
        # Two locks are required to coexist safely with rotate-activity-log.py:
        #
        # 1) Sidecar rotation lock (.<stem>.rotation.lock, same dir as the log).
        #    Rotation holds this across its read-plan-apply cycle. If the hook
        #    appended to the source between rotation's read and its os.replace,
        #    those appends would be written to the about-to-be-discarded inode
        #    and lost. Matching rotation's lock serializes hook appends against
        #    the entire rotation, guaranteeing no lost writes at the cost of
        #    brief (rare) blocking when a rotation is in flight.
        #
        # 2) Byte-range lock on the active log itself. Still needed so parallel
        #    hooks (no rotation running) don't interleave partial JSONL lines.
        #
        # On Windows msvcrt.locking is exclusive-only, so the hook serializes
        # with rotation one-for-one; rotation is rare (threshold > 10k lines)
        # and fast, so this is acceptable.
        rotation_lock_path = log_path.parent / f".{log_path.stem}.rotation.lock"
        with rotation_lock_path.open("a+", encoding="utf-8") as rot_lock:
            _lock_exclusive(rot_lock)
            try:
                # Open the log AFTER acquiring the rotation lock so we never
                # hold a handle to an inode rotation is about to os.replace.
                with log_path.open("a", encoding="utf-8", newline="\n") as handle:
                    _lock_exclusive(handle)
                    try:
                        handle.seek(0, os.SEEK_END)
                        handle.write(line)
                        handle.flush()
                    finally:
                        _unlock(handle)
            finally:
                _unlock(rot_lock)
        return 0
    except json.JSONDecodeError as exc:
        print(
            f"post-tool-use-log failed: stdin JSON parse error at "
            f"line {exc.lineno} col {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"post-tool-use-log failed: invalid input: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(
            f"post-tool-use-log failed: filesystem error ({exc.__class__.__name__}) "
            f"on {exc.filename!r}: {exc.strerror or exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"post-tool-use-log failed: unexpected {exc.__class__.__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
