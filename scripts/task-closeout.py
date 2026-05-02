#!/usr/bin/env python3
"""Run the agent-owned closeout checks for a task and optionally record evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


PROFILES = {"auto", "docs", "scripts", "reference", "copy", "runtime", "all"}


@dataclass
class CloseoutCheck:
    name: str
    status: str
    command: list[str]
    exit_code: int
    detail: str
    duration_s: float


@dataclass
class CloseoutResult:
    root: str
    goal: str
    profile: str
    changed_paths: list[str]
    checks: list[dict[str, Any]]
    recorded: bool
    evidence_path: str
    skills: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_run_id() -> str:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")
    return f"closeout-{stamp}"


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def first_lines(text: str, *, max_lines: int = 4) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:max_lines])


def resolve_under_root(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    resolved.relative_to(root.resolve())
    return resolved


def normalize_paths(root: Path, values: list[str]) -> list[str]:
    if not values:
        return ["."]
    result: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        normalized = resolve_under_root(root, stripped).relative_to(root.resolve()).as_posix()
        if normalized not in result:
            result.append(normalized)
    return result or ["."]


def unique_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def infer_profile(paths: list[str]) -> str:
    if not paths or paths == ["."]:
        return "all"
    if any(path.startswith("scripts/") or path.startswith("tests/") for path in paths):
        return "scripts"
    if any(path.startswith("research/reference-candidates/") for path in paths):
        return "reference"
    if any(path.startswith("runtime/proposals/reference-adoption/") or path == "runtime/reference-copy-ledger.jsonl" for path in paths):
        return "copy"
    if any(path.startswith("runtime/") for path in paths):
        return "runtime"
    if any(path.endswith(".md") or path.startswith("docs/") or path.startswith("rules/") for path in paths):
        return "docs"
    return "all"


def profile_commands(root: Path, profile: str) -> list[tuple[str, list[str]]]:
    py = sys.executable
    commands: dict[str, list[str]] = {}

    def add(name: str, command: list[str]) -> None:
        commands.setdefault(name, command)

    if profile in {"docs", "all"}:
        add("verify-skeleton", [py, str(root / "scripts" / "verify-skeleton.py"), "--root", str(root)])
        add("agent-autonomy-check", [py, str(root / "scripts" / "agent-autonomy-check.py"), "--root", str(root), "--strict"])
    if profile in {"scripts"}:
        add("verify-skeleton", [py, str(root / "scripts" / "verify-skeleton.py"), "--root", str(root)])
        add("agent-autonomy-check", [py, str(root / "scripts" / "agent-autonomy-check.py"), "--root", str(root), "--strict"])
        add("python-unittest", [py, "-m", "unittest", "discover", "-s", "tests", "-v"])
        add("security-scan", [py, str(root / "scripts" / "security-scan.py"), "--root", str(root), "--include-runtime", "--strict"])
    if profile in {"reference", "copy", "all"}:
        add("validate-reference-candidates", [py, str(root / "scripts" / "validate-reference-candidates.py"), "--root", str(root)])
        add("validate-reference-proposals", [py, str(root / "scripts" / "validate-reference-proposals.py"), "--root", str(root)])
    if profile in {"copy", "all"}:
        add("reference-copy-ledger", [py, str(root / "scripts" / "reference-copy-ledger.py"), "--root", str(root), "check"])
        add("security-scan", [py, str(root / "scripts" / "security-scan.py"), "--root", str(root), "--include-runtime", "--strict"])
    if profile in {"runtime", "all"}:
        add("verify-skeleton", [py, str(root / "scripts" / "verify-skeleton.py"), "--root", str(root)])
        add("completion-evidence", [py, str(root / "scripts" / "completion-evidence.py"), "--root", str(root), "check"])
        add("resume-readiness", [py, str(root / "scripts" / "resume-readiness.py"), "--root", str(root), "--strict"])
        add("skill-surface", [py, str(root / "scripts" / "skill-surface-check.py"), "--root", str(root), "--strict"])
    if profile == "all":
        add("quality-gate", [py, str(root / "scripts" / "quality-gate.py"), "--root", str(root), "--format", "json"])
    return list(commands.items())


def run_command(root: Path, name: str, command: list[str], timeout: int) -> CloseoutCheck:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=command_env(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CloseoutCheck(name, "FAIL", command, 124, f"timed out after {timeout}s", round(time.monotonic() - started, 3))
    output = first_lines((result.stdout or "") + "\n" + (result.stderr or ""))
    status = "OK" if result.returncode == 0 else "FAIL"
    return CloseoutCheck(name, status, command, result.returncode, output or f"exit {result.returncode}", round(time.monotonic() - started, 3))


def parse_prevalidated_check(value: str) -> CloseoutCheck:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("--prevalidated-check must be a JSON object")
    name = str(payload.get("name", "")).strip()
    status = str(payload.get("status", "")).strip().upper()
    if not name:
        raise ValueError("--prevalidated-check missing name")
    if status not in {"OK", "PASS", "WARN", "SKIP", "FAIL", "ERROR"}:
        raise ValueError(f"--prevalidated-check invalid status: {status}")
    command_value = payload.get("command", [])
    command = [str(item) for item in command_value] if isinstance(command_value, list) else [str(command_value)]
    exit_code = int(payload.get("exit_code", 0 if status in {"OK", "PASS"} else 1))
    detail = str(payload.get("detail", "")).strip() or "prevalidated"
    duration = float(payload.get("duration_s", 0.0) or 0.0)
    normalized_status = "OK" if status == "PASS" else "FAIL" if status == "ERROR" else status
    return CloseoutCheck(name, normalized_status, command, exit_code, detail, round(duration, 3))


def record_skill_use(root: Path, skill: str, run_id: str, outcome: str, goal: str, evidence_ref: str) -> bool:
    script = root / "scripts" / "skill-lifecycle.py"
    command = [
        sys.executable,
        str(script),
        "--root",
        str(root),
        "record-use",
        "--skill",
        skill,
        "--run-id",
        run_id,
        "--outcome",
        outcome,
        "--goal-lineage",
        goal,
        "--evidence-ref",
        evidence_ref,
    ]
    result = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=command_env(),
        timeout=60,
    )
    return result.returncode == 0


def record_evidence(root: Path, goal: str, changed_paths: list[str], checks: list[CloseoutCheck], residual_risk: str, skills: list[str]) -> tuple[bool, str]:
    script = root / "scripts" / "completion-evidence.py"
    run_id = utc_run_id()
    checks_ok = all(check.status == "OK" for check in checks)
    validations = [
        json.dumps(
            {
                "name": check.name,
                "command": " ".join(check.command),
                "status": check.status,
                "exit_code": check.exit_code,
                "detail": check.detail,
            },
            ensure_ascii=False,
        )
        for check in checks
    ]
    command = [sys.executable, str(script), "--root", str(root), "add", "--goal", goal]
    for path in changed_paths:
        command.extend(["--changed-path", path])
    for validation in validations:
        command.extend(["--validation", validation])
    command.extend(["--outcome", "genuine_success" if checks_ok else "partial_progress"])
    command.extend(["--residual-risk", residual_risk])
    result = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=command_env(),
        timeout=60,
    )
    if result.returncode != 0:
        return False, (root / "runtime" / "completion-evidence.jsonl").relative_to(root).as_posix()
    evidence_ref = (root / "runtime" / "completion-evidence.jsonl").relative_to(root).as_posix()
    skill_outcome = "success" if checks_ok else "failure"
    for skill in skills:
        if not record_skill_use(root, skill, run_id, skill_outcome, goal, evidence_ref):
            return False, (root / "runtime" / "skill-usage.jsonl").relative_to(root).as_posix()
    snapshot = root / "scripts" / "session-snapshot.py"
    if snapshot.exists():
        snapshot_result = subprocess.run(
            [sys.executable, str(snapshot), "--root", str(root), "write"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=command_env(),
            timeout=60,
        )
        if snapshot_result.returncode != 0:
            return False, (root / "runtime" / "session-snapshot.json").relative_to(root).as_posix()
    return True, evidence_ref


def render_text(result: CloseoutResult) -> str:
    lines = [
        "Task Closeout",
        f"root: {result.root}",
        f"goal: {result.goal}",
        f"profile: {result.profile}",
        f"changed_paths: {', '.join(result.changed_paths)}",
        f"skills: {', '.join(result.skills) if result.skills else '(none)'}",
    ]
    for check in result.checks:
        lines.append(f"  {check['status']:<4} {check['name']}: {check['detail']}")
    lines.append(f"recorded: {result.recorded}")
    if result.evidence_path:
        lines.append(f"evidence_path: {result.evidence_path}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--goal", required=True, help="Short task goal for closeout evidence.")
    parser.add_argument("--changed-path", action="append", default=[], help="Changed path, repeatable.")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="auto")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--record", dest="record", action="store_true", help="Append completion evidence.")
    parser.add_argument("--no-record", dest="record", action="store_false", help="Do not append completion evidence.")
    parser.add_argument("--residual-risk", default="")
    parser.add_argument("--skill", action="append", default=[], help="Skill used by this task, repeatable. Only recorded with --record.")
    parser.add_argument("--prevalidated-check", action="append", default=[], help="Validation JSON from an upstream gate; skips local profile checks when present.")
    parser.set_defaults(record=False)
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    try:
        changed_paths = normalize_paths(root, args.changed_path)
    except ValueError as exc:
        print(f"changed path must stay inside project root {root}: {exc}", file=sys.stderr)
        return 2

    profile = infer_profile(changed_paths) if args.profile == "auto" else args.profile
    try:
        checks = [parse_prevalidated_check(value) for value in args.prevalidated_check]
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"invalid prevalidated check: {exc}", file=sys.stderr)
        return 2
    if checks:
        profile = "prevalidated"
    else:
        checks = [run_command(root, name, command, args.timeout) for name, command in profile_commands(root, profile)]
    skills = unique_values(args.skill)
    recorded = False
    evidence = ""
    if args.record:
        recorded, evidence = record_evidence(root, args.goal, changed_paths, checks, args.residual_risk, skills)
    result = CloseoutResult(
        root=str(root),
        goal=args.goal,
        profile=profile,
        changed_paths=changed_paths,
        checks=[asdict(check) for check in checks],
        recorded=recorded,
        evidence_path=evidence,
        skills=skills,
    )
    if args.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 1 if any(check.status == "FAIL" for check in checks) or (args.record and not recorded) else 0


if __name__ == "__main__":
    raise SystemExit(main())
