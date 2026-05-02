#!/usr/bin/env python3
"""Run the canonical verify gate: check -> lint -> unit -> smoke -> integration."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


@dataclass
class StageResult:
    stage: str
    status: str
    command: list[str]
    detail: str
    duration_s: float


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_command(root: Path, stage: str, command: list[str], timeout: int) -> StageResult:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return StageResult(stage, "FAIL", command, f"timed out after {timeout}s", round(time.monotonic() - started, 3))
    output = "\n".join(line for line in (result.stdout + "\n" + result.stderr).splitlines() if line.strip())
    detail = " | ".join(output.splitlines()[:5]) or f"exit {result.returncode}"
    return StageResult(stage, "PASS" if result.returncode == 0 else "FAIL", command, detail, round(time.monotonic() - started, 3))


def smoke_bootstrap(root: Path, timeout: int) -> StageResult:
    tmp = Path(tempfile.mkdtemp(prefix="ai-architecture-smoke-"))
    target = tmp / "project"
    try:
        command = [
            sys.executable,
            str(root / "scripts" / "bootstrap" / "new-project.py"),
            "--name",
            "smoke",
            "--target",
            str(target),
            "--domain",
            "cli",
            "--stack",
            "python",
        ]
        result = run_command(root, "smoke", command, timeout)
        if result.status != "PASS":
            return result
        verify = run_command(
            root,
            "smoke",
            [sys.executable, str(root / "scripts" / "verify-skeleton.py"), "--root", str(target), "--skip-wiki-lint"],
            timeout,
        )
        if verify.status != "PASS":
            return verify
        parity = run_command(
            root,
            "smoke",
            [sys.executable, str(root / "scripts" / "verify-parity.py"), "--root", str(target)],
            timeout,
        )
        if parity.status != "PASS":
            return parity
        snapshot = run_command(
            root,
            "smoke",
            [sys.executable, str(root / "scripts" / "session-snapshot.py"), "--root", str(target), "check"],
            timeout,
        )
        if snapshot.status != "PASS":
            return snapshot
        return verify
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_verify(root: Path, timeout: int, skip_unit: bool) -> list[StageResult]:
    results: list[StageResult] = []
    stages = [
        ("check", [sys.executable, str(root / "scripts" / "verify-skeleton.py"), "--root", str(root), "--skip-wiki-lint"]),
        ("lint", [sys.executable, str(root / "scripts" / "skill-surface-check.py"), "--root", str(root), "--strict"]),
    ]
    for stage, command in stages:
        result = run_command(root, stage, command, timeout)
        results.append(result)
        if result.status != "PASS":
            return results
    if not skip_unit:
        result = run_command(root, "unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], timeout)
        results.append(result)
        if result.status != "PASS":
            return results
    smoke = smoke_bootstrap(root, timeout)
    results.append(smoke)
    if smoke.status != "PASS":
        return results
    integration = run_command(root, "integration", [sys.executable, str(root / "scripts" / "verify-parity.py"), "--root", str(root)], timeout)
    results.append(integration)
    return results


def render_text(results: list[StageResult]) -> str:
    lines = ["Verify Gate"]
    for result in results:
        lines.append(f"  {result.status:<4} {result.stage}: {result.detail}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--timeout", type=int, default=180, help="Per-stage timeout in seconds.")
    parser.add_argument("--skip-unit", action="store_true", help="Skip unittest discovery.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    results = run_verify(root, args.timeout, args.skip_unit)
    if args.format == "json":
        print(json.dumps({"root": str(root), "results": [asdict(r) for r in results]}, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))
    return 1 if any(result.status != "PASS" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
