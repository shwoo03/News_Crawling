#!/usr/bin/env python3
"""Run the local quality gate for a skeleton-based project.

The gate auto-detects available validation surfaces and runs only what exists:
skeleton verification, review queue count, Python syntax checks, unittest, and
package.json test/build scripts. It is read-only and standard-library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import tokenize
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
FAILURE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("timeout", ("timed out", "timeout", "deadline exceeded")),
    ("auth", ("unauthorized", "authentication", "forbidden", "invalid api key", "permission denied")),
    ("quota", ("rate limit", "quota", "too many requests", "429", "insufficient credits")),
    ("format", ("jsondecode", "invalid json", "parse error", "schema", "frontmatter", "yaml")),
    ("payload", ("payload too large", "request entity too large", "maximum context", "context length", "too many tokens")),
    ("policy", ("blocked by policy", "confirmation required", "outside repo", "not allowed", "denied by policy")),
    ("infra", ("connection refused", "dns", "network", "no such file", "not found", "exit 127", "broken pipe")),
]


@dataclass
class GateCheck:
    name: str
    status: str
    detail: str
    command: list[str]
    duration_s: float = 0.0


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def should_skip_path(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in SKIP_DIR_NAMES for part in parts)


def first_lines(text: str, *, max_lines: int = 4) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:max_lines])


def classify_failure(text: str) -> str:
    haystack = text.lower()
    for category, needles in FAILURE_RULES:
        if any(needle in haystack for needle in needles):
            return category
    return "unknown"


def run_command(root: Path, command: list[str], timeout: int) -> GateCheck:
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
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        return GateCheck(
            name=command_name(command),
            status="FAIL",
            detail=f"timed out after {timeout}s",
            command=command,
            duration_s=round(duration, 3),
        )
    duration = time.monotonic() - started
    output = first_lines((result.stdout or "") + "\n" + (result.stderr or ""))
    status = "OK" if result.returncode == 0 else "FAIL"
    detail = output or f"exit {result.returncode}"
    if status == "FAIL":
        detail = f"{detail} [failure_type={classify_failure((result.stdout or '') + chr(10) + (result.stderr or ''))}]"
    return GateCheck(
        name=command_name(command),
        status=status,
        detail=detail,
        command=command,
        duration_s=round(duration, 3),
    )


def command_name(command: list[str]) -> str:
    if not command:
        return "unknown"
    joined = " ".join(command)
    if "verify-skeleton.py" in joined:
        return "verify-skeleton"
    if "agent-autonomy-check.py" in joined:
        return "agent-autonomy"
    if "completion-evidence.py" in joined:
        return "completion-evidence"
    if "security-scan.py" in joined:
        return "security-scan"
    if "resume-readiness.py" in joined:
        return "resume-readiness"
    if "skill-surface-check.py" in joined:
        return "skill-surface"
    if "install-state.py" in joined:
        return "install-state"
    if "skill-lifecycle.py" in joined:
        return "skill-lifecycle"
    if "eval-all.py" in joined:
        return "eval-all"
    if "cost-log.py" in joined:
        return "cost-log"
    if "session-snapshot.py" in joined:
        return "session-snapshot"
    if "reference-task-queue.py" in joined:
        return "reference-task-queue"
    if "session-recall.py" in joined:
        return "session-recall"
    if "review-queue.py" in joined:
        return "review-queue"
    if "portability-scan.py" in joined:
        return "portability-scan"
    if "checkpoint.py" in joined:
        return "checkpoint"
    if "tool-health.py" in joined:
        return "tool-health"
    if "tool-guardrail.py" in joined:
        return "tool-guardrail"
    if "path-safety.py" in joined:
        return "path-safety"
    if "install-profiles.py" in joined:
        return "install-profiles"
    if "skill-stocktake.py" in joined:
        return "skill-stocktake"
    if "mcp-audit.py" in joined:
        return "mcp-audit"
    if "permission-evaluate.py" in joined:
        return "permission-evaluate"
    if "plugin-manifest-check.py" in joined:
        return "plugin-manifest"
    if "schema-check.py" in joined:
        return "schema-check"
    if "markdown-sanitize.py" in joined:
        return "markdown-sanitize"
    if "failure-classify.py" in joined:
        return "failure-classify"
    if "change-drift-check.py" in joined:
        return "change-drift-check"
    if "unittest" in joined:
        return "python-unittest"
    if len(command) >= 2 and command[0] == "npm":
        return f"npm-{command[-1]}"
    return Path(command[0]).name


def check_python_syntax(root: Path) -> GateCheck:
    started = time.monotonic()
    targets: list[Path] = []
    for folder in ("scripts", "tests"):
        base = root / folder
        if base.is_dir():
            targets.extend(path for path in base.rglob("*.py") if not should_skip_path(path, root))
    if not targets:
        return GateCheck("python-syntax", "SKIP", "no scripts/ or tests/ Python files", [], 0.0)
    failures: list[str] = []
    for path in sorted(targets):
        try:
            with tokenize.open(path) as handle:
                source = handle.read()
            compile(source, str(path), "exec")
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            failures.append(f"{path.relative_to(root).as_posix()}: {exc}")
    duration = round(time.monotonic() - started, 3)
    if failures:
        return GateCheck("python-syntax", "FAIL", " | ".join(failures[:3]), [], duration)
    return GateCheck("python-syntax", "OK", f"{len(targets)} Python file(s) parsed", [], duration)


def check_verify_skeleton(root: Path, timeout: int) -> GateCheck:
    script = root / "scripts" / "verify-skeleton.py"
    if not script.exists():
        return GateCheck("verify-skeleton", "SKIP", "scripts/verify-skeleton.py not found", [], 0.0)
    check = run_command(root, [sys.executable, str(script), "--root", str(root)], timeout)
    if check.status == "OK" and ("WARN" in check.detail or "skeleton findings:" in check.detail):
        check.status = "WARN"
    return check


def check_review_queue(root: Path, timeout: int) -> GateCheck:
    script = root / "scripts" / "review-queue.py"
    if not script.exists():
        return GateCheck("review-queue", "SKIP", "scripts/review-queue.py not found", [], 0.0)
    command = [sys.executable, str(script), "--root", str(root), "count", "--json"]
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=str(root), capture_output=True, text=True, encoding="utf-8", env=command_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return GateCheck("review-queue", "FAIL", f"timed out after {timeout}s", command, round(time.monotonic() - started, 3))
    duration = round(time.monotonic() - started, 3)
    if completed.returncode != 0:
        return GateCheck("review-queue", "FAIL", first_lines((completed.stdout or "") + "\n" + (completed.stderr or "")), command, duration)
    try:
        payload = json.loads(completed.stdout)
        open_count = int(payload.get("open", 0))
        deferred_count = int(payload.get("deferred", 0))
    except (ValueError, json.JSONDecodeError, AttributeError):
        return GateCheck("review-queue", "WARN", f"unexpected count output: {first_lines(completed.stdout)}", command, duration)
    if open_count:
        return GateCheck("review-queue", "WARN", f"{open_count} open review item(s), {deferred_count} deferred", command, duration)
    if deferred_count:
        return GateCheck("review-queue", "OK", f"0 open review items, {deferred_count} deferred", command, duration)
    return GateCheck("review-queue", "OK", "0 open review items, 0 deferred", command, duration)


def check_script_command(root: Path, script_name: str, args: list[str], timeout: int) -> GateCheck:
    script = root / "scripts" / script_name
    if not script.exists():
        return GateCheck(Path(script_name).stem, "SKIP", f"scripts/{script_name} not found", [], 0.0)
    return run_command(root, [sys.executable, str(script), "--root", str(root), *args], timeout)


def check_json_findings_tool(root: Path, script_name: str, args: list[str], timeout: int, *, strict: bool, name: str) -> GateCheck:
    script = root / "scripts" / script_name
    if not script.exists():
        return GateCheck(name, "SKIP", f"scripts/{script_name} not found", [], 0.0)
    command = [sys.executable, str(script), "--root", str(root), "--format", "json", *args]
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=str(root), capture_output=True, text=True, encoding="utf-8", env=command_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return GateCheck(name, "FAIL", f"timed out after {timeout}s", command, round(time.monotonic() - started, 3))
    duration = round(time.monotonic() - started, 3)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        status = "FAIL" if completed.returncode else "WARN"
        return GateCheck(name, status, first_lines((completed.stdout or "") + "\n" + (completed.stderr or "")), command, duration)
    findings = payload.get("findings") if isinstance(payload, dict) else []
    count = len(findings) if isinstance(findings, list) else 0
    if completed.returncode != 0 and not count:
        return GateCheck(name, "FAIL", first_lines((completed.stdout or "") + "\n" + (completed.stderr or "")), command, duration)
    if count:
        return GateCheck(name, "FAIL" if strict else "WARN", f"{count} finding(s)", command, duration)
    return GateCheck(name, "OK", "no findings", command, duration)


def check_tool_guardrail(root: Path, timeout: int, *, strict: bool) -> GateCheck:
    script = root / "scripts" / "tool-guardrail.py"
    if not script.exists():
        return GateCheck("tool-guardrail", "SKIP", "scripts/tool-guardrail.py not found", [], 0.0)
    command = [sys.executable, str(script), "--root", str(root), "--format", "json"]
    if strict:
        command.append("--strict")
    command.append("check")
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=str(root), capture_output=True, text=True, encoding="utf-8", env=command_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return GateCheck("tool-guardrail", "FAIL", f"timed out after {timeout}s", command, round(time.monotonic() - started, 3))
    duration = round(time.monotonic() - started, 3)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return GateCheck("tool-guardrail", "FAIL" if completed.returncode else "WARN", first_lines((completed.stdout or "") + "\n" + (completed.stderr or "")), command, duration)
    findings = payload.get("findings") if isinstance(payload, dict) else []
    repeated = payload.get("repeated_failures") if isinstance(payload, dict) else []
    if findings:
        return GateCheck("tool-guardrail", "FAIL", f"{len(findings)} parse finding(s)", command, duration)
    severe = [item for item in repeated if isinstance(item, dict) and item.get("action") in {"block", "halt"}]
    if severe:
        return GateCheck("tool-guardrail", "FAIL" if strict else "WARN", f"{len(severe)} repeated failure group(s)", command, duration)
    warned = [item for item in repeated if isinstance(item, dict) and item.get("action") == "warn"]
    if warned:
        return GateCheck("tool-guardrail", "WARN", f"{len(warned)} warning group(s)", command, duration)
    return GateCheck("tool-guardrail", "OK", "no repeated tool failures", command, duration)


def check_eval_all(root: Path, timeout: int) -> GateCheck:
    script = root / "scripts" / "eval-all.py"
    if not script.exists():
        return GateCheck("eval-all", "SKIP", "scripts/eval-all.py not found", [], 0.0)
    command = [sys.executable, str(script), "--root", str(root), "--format", "json"]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=command_env(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return GateCheck("eval-all", "FAIL", f"timed out after {timeout}s", command, round(time.monotonic() - started, 3))
    duration = round(time.monotonic() - started, 3)
    output = first_lines((completed.stdout or "") + "\n" + (completed.stderr or ""))
    if completed.returncode != 0:
        return GateCheck("eval-all", "FAIL", output or f"exit {completed.returncode}", command, duration)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return GateCheck("eval-all", "OK", output or "eval-all completed", command, duration)
    results = payload.get("results") if isinstance(payload, dict) else []
    if isinstance(results, list):
        warn_count = sum(1 for item in results if isinstance(item, dict) and item.get("status") == "WARN")
        fail_count = sum(1 for item in results if isinstance(item, dict) and item.get("status") == "FAIL")
        if fail_count:
            return GateCheck("eval-all", "FAIL", f"{fail_count} fail, {warn_count} warn", command, duration)
        if warn_count:
            return GateCheck("eval-all", "WARN", f"{fail_count} fail, {warn_count} warn", command, duration)
        return GateCheck("eval-all", "OK", f"{fail_count} fail, {warn_count} warn", command, duration)
    return GateCheck("eval-all", "OK", output or "eval-all completed", command, duration)


def check_portability(root: Path, timeout: int) -> GateCheck:
    script = root / "scripts" / "portability-scan.py"
    if not script.exists():
        return GateCheck("portability-scan", "SKIP", "scripts/portability-scan.py not found", [], 0.0)
    command = [sys.executable, str(script), "--root", str(root), "--format", "json"]
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=str(root), capture_output=True, text=True, encoding="utf-8", env=command_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return GateCheck("portability-scan", "FAIL", f"timed out after {timeout}s", command, round(time.monotonic() - started, 3))
    duration = round(time.monotonic() - started, 3)
    if completed.returncode != 0:
        return GateCheck("portability-scan", "FAIL", first_lines((completed.stdout or "") + "\n" + (completed.stderr or "")), command, duration)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return GateCheck("portability-scan", "WARN", f"unexpected output: {first_lines(completed.stdout)}", command, duration)
    count = int(payload.get("count", 0)) if isinstance(payload, dict) else 0
    if count:
        return GateCheck("portability-scan", "WARN", f"{count} machine-specific path finding(s)", command, duration)
    return GateCheck("portability-scan", "OK", "no machine-specific paths found", command, duration)


def check_unittest(root: Path, timeout: int) -> GateCheck:
    if not (root / "tests").is_dir():
        return GateCheck("python-unittest", "SKIP", "tests/ directory not found", [], 0.0)
    return run_command(root, [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], timeout)


def package_json_scripts(root: Path) -> dict[str, str]:
    path = root / "package.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    scripts = payload.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def check_node_scripts(root: Path, timeout: int) -> list[GateCheck]:
    scripts = package_json_scripts(root)
    if not scripts:
        return [GateCheck("node-scripts", "SKIP", "package.json scripts not found", [], 0.0)]
    if not shutil.which("npm"):
        return [GateCheck("node-scripts", "WARN", "npm not found on PATH", [], 0.0)]
    checks: list[GateCheck] = []
    for script_name in ("test", "build"):
        if script_name in scripts:
            checks.append(run_command(root, ["npm", "run", script_name], timeout))
    if not checks:
        checks.append(GateCheck("node-scripts", "SKIP", "no npm test/build scripts", [], 0.0))
    return checks


def check_codemap_freshness(root: Path) -> GateCheck:
    index = root / "docs" / "CODEMAPS" / "INDEX.md"
    if not index.exists():
        return GateCheck("codemap-freshness", "WARN", "docs/CODEMAPS/INDEX.md not found; run scripts/generate-codemaps.py --write", [], 0.0)
    try:
        index_mtime = index.stat().st_mtime
    except OSError as exc:
        return GateCheck("codemap-freshness", "WARN", f"could not stat codemap index: {exc}", [], 0.0)
    newer: list[str] = []
    watched_roots = ["scripts", "skills", "agents", "rules", "docs", "tests"]
    for rel in watched_roots:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_dir() or should_skip_path(path, root):
                continue
            if "docs/CODEMAPS" in path.as_posix():
                continue
            try:
                if path.stat().st_mtime > index_mtime:
                    newer.append(path.relative_to(root).as_posix())
            except OSError:
                continue
            if len(newer) >= 5:
                break
        if len(newer) >= 5:
            break
    if newer:
        return GateCheck("codemap-freshness", "WARN", "codemaps may be stale; newer files: " + ", ".join(newer), [], 0.0)
    return GateCheck("codemap-freshness", "OK", "docs/CODEMAPS appears current by mtime", [], 0.0)


def run_gate(args: argparse.Namespace) -> list[GateCheck]:
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        raise SystemExit(f"root not a directory: {root}")
    checks: list[GateCheck] = []
    if not args.skip_skeleton:
        checks.append(check_verify_skeleton(root, args.timeout))
    checks.append(check_script_command(root, "agent-autonomy-check.py", ["--strict"], args.timeout))
    checks.append(check_review_queue(root, args.timeout))
    checks.append(check_script_command(root, "completion-evidence.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "security-scan.py", ["--include-runtime", "--strict"], args.timeout))
    checks.append(check_script_command(root, "resume-readiness.py", ["--strict"], args.timeout))
    checks.append(check_script_command(root, "skill-surface-check.py", ["--strict"], args.timeout))
    install_args = ["check", "--strict"] if args.strict else ["check"]
    checks.append(check_script_command(root, "install-state.py", install_args, args.timeout))
    checks.append(check_script_command(root, "reference-task-queue.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "skill-lifecycle.py", ["report"], args.timeout))
    checks.append(check_eval_all(root, args.timeout))
    checks.append(check_script_command(root, "cost-log.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "session-snapshot.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "session-recall.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "checkpoint.py", ["check"], args.timeout))
    checks.append(check_json_findings_tool(root, "tool-health.py", ["check"], args.timeout, strict=args.strict, name="tool-health"))
    checks.append(check_tool_guardrail(root, args.timeout, strict=args.strict))
    checks.append(check_json_findings_tool(root, "mcp-audit.py", ["check"], args.timeout, strict=args.strict, name="mcp-audit"))
    checks.append(check_script_command(root, "permission-evaluate.py", ["evaluate", "--action", "shell", "--resource", "*"], args.timeout))
    checks.append(check_script_command(root, "path-safety.py", ["check", "--path", "scripts/agent-flow.py", "--operation", "write"], args.timeout))
    checks.append(check_script_command(root, "install-profiles.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "skill-stocktake.py", ["report"], args.timeout))
    checks.append(check_script_command(root, "plugin-manifest-check.py", ["check"], args.timeout))
    checks.append(check_script_command(root, "schema-check.py", ["check"], args.timeout))
    checks.append(check_json_findings_tool(root, "markdown-sanitize.py", ["--check"], args.timeout, strict=args.strict, name="markdown-sanitize"))
    checks.append(run_command(root, [sys.executable, str(root / "scripts" / "failure-classify.py"), "--text", "timeout while running validation", "--format", "json"], args.timeout))
    checks.append(check_json_findings_tool(root, "change-drift-check.py", [], args.timeout, strict=args.strict, name="change-drift-check"))
    checks.append(check_portability(root, args.timeout))
    checks.append(check_codemap_freshness(root))
    checks.append(check_python_syntax(root))
    if not args.skip_tests:
        checks.append(check_unittest(root, args.timeout))
    if not args.skip_node:
        checks.extend(check_node_scripts(root, args.timeout))
    return checks


def render_text(root: Path, checks: list[GateCheck], strict: bool) -> str:
    counts = Counter(check.status for check in checks)
    lines = [
        "Quality Gate",
        f"root: {root}",
        f"summary: {counts.get('FAIL', 0)} fail, {counts.get('WARN', 0)} warn, {counts.get('OK', 0)} ok, {counts.get('SKIP', 0)} skip",
    ]
    for check in checks:
        command = " ".join(check.command) if check.command else "-"
        lines.append(f"  {check.status:<4} {check.name}: {check.detail}")
        lines.append(f"       command: {command}")
    if strict and counts.get("WARN", 0):
        lines.append("strict mode: warnings make the gate fail")
    return "\n".join(lines)


def render_json(root: Path, checks: list[GateCheck]) -> str:
    payload: dict[str, Any] = {
        "root": str(root),
        "summary": dict(sorted(Counter(check.status for check in checks).items())),
        "checks": [asdict(check) for check in checks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--timeout", type=int, default=120, help="Per-command timeout in seconds.")
    parser.add_argument("--strict", action="store_true", help="Fail when warnings are present.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unittest discovery.")
    parser.add_argument("--skip-node", action="store_true", help="Skip package.json npm scripts.")
    parser.add_argument("--skip-skeleton", action="store_true", help="Skip verify-skeleton.py.")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    checks = run_gate(args)
    if args.format == "json":
        print(render_json(root, checks))
    else:
        print(render_text(root, checks, args.strict))
    has_fail = any(check.status == "FAIL" for check in checks)
    has_warn = any(check.status == "WARN" for check in checks)
    return 1 if has_fail or (args.strict and has_warn) else 0


if __name__ == "__main__":
    raise SystemExit(main())
