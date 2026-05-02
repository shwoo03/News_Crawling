#!/usr/bin/env python3
"""Detect documentation that pushes routine execution back to the user.

This checker protects the skeleton's core operating contract: users provide
goals, constraints, and approvals through chat; agents run feasible commands,
edit files, validate results, and record evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


DOC_TARGETS = (
    "AGENTS.md",
    "CLAUDE.md",
    "docs",
    "rules",
    "scripts/README.md",
    "research/reference-candidates/README.md",
    "runtime/proposals/reference-adoption/README.md",
)
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
SUSPICIOUS_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "user_runs_command",
        re.compile(
            r"(?:사용자[^\n]{0,48}(?:직접|수동)[^\n]{0,96}(?:실행|명령|(?<!나)머지|merge)|"
            r"(?:ask|tell|instruct)\s+the\s+user\s+to\s+(?:run|execute)|"
            r"user\s+(?:must|should|needs?\s+to)\s+(?:run|execute|merge)|"
            r"manual\s+user\s+(?:command|merge|execution))",
            re.IGNORECASE,
        ),
        "routine command execution appears assigned to the user",
    ),
    (
        "user_edits_operational_artifact",
        re.compile(
            r"(?:사용자[^\n]{0,48}(?:직접|수동)[^\n]{0,96}(?:수정|편집|작성)|"
            r"user\s+(?:must|should|needs?\s+to)\s+(?:edit|write|update)\s+"
            r"(?:the\s+)?(?:ledger|handoff|activity log|proposal|candidate))",
            re.IGNORECASE,
        ),
        "routine operational artifact editing appears assigned to the user",
    ),
)
ALLOW_CONTEXT_RE = re.compile(
    r"(?:아니|아닙|않|예외|불가능|권한 밖|채팅|승인|거절|목표|제약|"
    r"agent(?:-| )run|agent responsibility|agent-run|not routine|should not|"
    r"normally should not|exception|cannot access|approval|direction|constraints)",
    re.IGNORECASE,
)


@dataclass
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str
    text: str


@dataclass
class CheckResult:
    root: str
    summary: dict[str, int]
    scanned_files: int
    findings: list[dict[str, object]]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts) or path.suffix.lower() != ".md"


def iter_doc_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for target in DOC_TARGETS:
        path = root / target
        if path.is_file() and not should_skip_path(path):
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in sorted(path.rglob("*.md")) if p.is_file() and not should_skip_path(p))
    return sorted(dict.fromkeys(files))


def line_allowed(line: str) -> bool:
    return bool(ALLOW_CONTEXT_RE.search(line))


def scan_file(root: Path, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    in_code_fence = False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence or line_allowed(line):
            continue
        for rule, pattern, message in SUSPICIOUS_RULES:
            if pattern.search(line):
                findings.append(
                    Finding(
                        "WARN",
                        rule,
                        rel(path, root),
                        index,
                        message,
                        stripped[:180],
                    )
                )
    return findings


def run_check(root: Path) -> CheckResult:
    files = iter_doc_files(root)
    findings: list[Finding] = []
    for path in files:
        findings.extend(scan_file(root, path))
    summary_counter = Counter(finding.severity for finding in findings)
    summary = {severity: summary_counter.get(severity, 0) for severity in ("ERROR", "WARN", "INFO")}
    return CheckResult(
        root=str(root),
        summary=summary,
        scanned_files=len(files),
        findings=[asdict(finding) for finding in findings],
    )


def render_text(result: CheckResult) -> str:
    lines = [
        "Agent Autonomy Check",
        f"root: {result.root}",
        "summary: " + ", ".join(f"{key.lower()}={value}" for key, value in result.summary.items()),
        f"scanned_files: {result.scanned_files}",
    ]
    if not result.findings:
        lines.append("findings: none")
        return "\n".join(lines)
    lines.append("findings:")
    for finding in result.findings:
        lines.append(
            f"  {finding['severity']:<5} {finding['path']}:{finding['line']} "
            f"{finding['rule']} - {finding['message']}"
        )
        lines.append(f"        text: {finding['text']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when findings are present.")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    result = run_check(root)
    if args.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 1 if args.strict and result.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
