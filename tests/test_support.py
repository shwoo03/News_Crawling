"""Smoke tests for the skeleton maintenance surface.

These tests are the minimum signal a skeleton maintainer needs before
merging a change to `scripts/*` or `docs/*`. Run:

    python -m unittest discover -s tests -v

Design constraints (intentional):

- No external deps. Standard library only, so a fresh checkout works.
- No network. Everything runs against the local tree and a tmpdir.
- Fast. Each test should complete in well under a second except the
  bootstrap integration test which does a tree copy.
- Isolated. The skeleton's own runtime/* files must not be mutated.
"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a python subprocess with utf-8 stdio so emoji/Korean in help text
    does not blow up on cp949 Windows consoles during the test run itself."""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )


def _run_bytes(
    argv: list[str], stdin_bytes: bytes, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    """Like _run but feeds raw bytes on stdin and returns raw byte streams.
    Needed for tests that must send a BOM or other non-text bytes without the
    text-mode codec stripping them first."""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(cwd) if cwd else None,
        input=stdin_bytes,
        capture_output=True,
        env=env,
        timeout=60,
    )


def _path_is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _make_external_tmpdir_or_skip(test_case: unittest.TestCase, prefix: str) -> Path:
    """Create a temp directory outside the repo using a subprocess probe.

    The bootstrap integration test intentionally refuses targets inside the
    skeleton tree. Some Codex sandboxes allow writes only under REPO_ROOT, so
    default tempfile locations either fail with PermissionError in subprocesses
    or cannot be cleaned up. In that case, skip the integration test instead of
    reporting a false regression.
    """
    base = Path(os.environ.get("SKELETON_TEST_EXTERNAL_TMP", tempfile.gettempdir()))
    if _path_is_under(base, REPO_ROOT):
        test_case.skipTest("no external temp root available outside the skeleton")
    target = base / f"{prefix}-{uuid.uuid4().hex}"
    probe = (
        "from pathlib import Path; import sys; "
        "p=Path(sys.argv[1]); p.mkdir(parents=True); "
        "(p/'probe.txt').write_text('ok', encoding='utf-8')"
    )
    result = _run(["-c", probe, str(target)])
    if result.returncode != 0:
        test_case.skipTest(
            "external temp root is not writable by subprocesses: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    return target

__all__ = [
    "os",
    "json",
    "shutil",
    "subprocess",
    "sys",
    "tempfile",
    "unittest",
    "uuid",
    "Path",
    "REPO_ROOT",
    "SCRIPTS",
    "_run",
    "_run_bytes",
    "_path_is_under",
    "_make_external_tmpdir_or_skip",
]
