#!/usr/bin/env python3
"""Session-scoped advisory locks for append-only runtime writes."""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import Iterator


class RuntimeLockError(RuntimeError):
    pass


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in name) or "runtime"


@contextlib.contextmanager
def runtime_lock(root: Path, name: str, *, timeout_s: float = 10.0, stale_after_s: float = 600.0) -> Iterator[Path]:
    """Acquire an exclusive lock file under runtime/locks.

    This is intentionally simple and stdlib-only. It protects our JSONL ledgers
    from concurrent append interleaving without pretending to be a distributed
    lock. Stale locks can be replaced after `stale_after_s`.
    """

    root = root.resolve(strict=False)
    lock_dir = root / "runtime" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{_safe_name(name)}.lock"
    started = time.monotonic()
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"pid={os.getpid()} ts={time.time()}\n".encode("utf-8"))
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_after_s:
                    lock_path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() - started >= timeout_s:
                raise RuntimeLockError(f"timed out acquiring runtime lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield lock_path
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
