#!/usr/bin/env python3
"""Scan skeleton files for machine-specific paths before reuse."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SKIP_DIRS = {
    ".git",
    ".codex",
    ".claude",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "runtime",
    "tests",
}
SKIP_PREFIXES = ("docs/CODEMAPS/",)
TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".py", ".sh", ".example", ""}
PATTERNS = (
    ("home_path", re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s)\"'`<>{}\\]+")),
    ("private_tmp", re.compile(r"/private/(?:tmp|var)/[^\s)\"'`<>{}\\]+")),
    ("windows_user_path", re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+\\\\[^\s)\"'`<>{}]+")),
)


@dataclass
class Finding:
    check: str
    path: str
    line: int
    match: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return True
    parts = path.relative_to(root).parts
    return any(part in SKIP_DIRS for part in parts) or any(rel.startswith(prefix) for prefix in SKIP_PREFIXES)


def is_text_candidate(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in {".env.example", "SECURITY.md"}


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() or should_skip(path, root) or not is_text_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            for check, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    findings.append(Finding(check, rel, line_no, match.group(0)))
    return findings


def render_text(findings: list[Finding], strict: bool) -> str:
    if not findings:
        return "portability scan OK: no machine-specific paths found"
    label = "ERROR" if strict else "WARN"
    lines = ["portability scan findings:"]
    for finding in findings[:50]:
        lines.append(f"  {label} [{finding.check}] {finding.path}:{finding.line} {finding.match}")
    if len(findings) > 50:
        lines.append(f"  ... {len(findings) - 50} more")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    findings = scan(root)
    payload = {"ok": not findings, "strict": args.strict, "count": len(findings), "findings": [asdict(item) for item in findings]}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings, args.strict))
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
