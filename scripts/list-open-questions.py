#!/usr/bin/env python3
"""Scan the project for [NEEDS CLARIFICATION: ...] markers and report them.

The `[NEEDS CLARIFICATION: <question>]` marker is defined in
`rules/common/README.md`. Agents and humans sprinkle it across docs when the
right next step requires user input. This tool aggregates every open marker in
one pass so the list can be reviewed as a dashboard.

- Default: print `file:line | question` rows, exit 0.
- `--strict`: exit 1 when any marker is present (CI gate).
- `--count`: print only the total number.
- `--by-file`: group by file with counts.
- `--json`: emit a JSON array for machine consumption.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Strict form from rules/common/README.md: the question text is required.
# Whitespace between "NEEDS" and "CLARIFICATION" is optional for tolerance.
MARKER_RE = re.compile(r"\[NEEDS\s+CLARIFICATION:\s*([^\]]+)\]")

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

# Path prefixes (relative, posix) to skip entirely.
SKIP_DIR_PREFIXES = (
    "runtime/archive/",
    "runtime/tmp-",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def should_skip(rel: str, path: Path) -> bool:
    parts = rel.split("/")
    if any(part in SKIP_DIR_NAMES for part in parts[:-1]):
        return True
    if any(part.startswith(("tmp-", "scratch-")) or "-smoke-" in part for part in parts):
        return True
    if any(rel.startswith(prefix) for prefix in SKIP_DIR_PREFIXES):
        return True
    # Don't flag the marker definition inside rules/common/README.md or the
    # template instructions that describe the marker format. Those mentions
    # of `[NEEDS CLARIFICATION: <specific question>]` are pedagogical, not
    # open questions. Heuristic: skip files that contain the literal text
    # `<specific question>` or `<question>` as the marker body.
    return False


def iter_markdown(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if should_skip(rel, path):
            continue
        files.append(path)
    return sorted(files)


def scan(root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in iter_markdown(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        in_fence = False
        for line_no, line in enumerate(text.splitlines(), start=1):
            # Track triple-backtick fenced blocks. Any marker inside a fence
            # is treated as pedagogical example (see the marker definition
            # in rules/common/README.md and PROJECT_PROFILE.template.md).
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in MARKER_RE.finditer(line):
                question = match.group(1).strip()
                # Skip placeholder examples like "<specific question>" /
                # "<question>" and literal "..." ellipses — those document
                # the marker format rather than raise a real question.
                if question.startswith("<") and question.endswith(">"):
                    continue
                if question in {"...", "…"}:
                    continue
                findings.append(
                    {
                        "file": rel,
                        "line": line_no,
                        "question": question,
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", default=None, help="Project root to scan (default: repo root).")
    parser.add_argument("--count", action="store_true", help="Print only the total count.")
    parser.add_argument("--by-file", action="store_true", help="Group findings by file with counts.")
    parser.add_argument("--json", action="store_true", help="Emit JSON array.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any marker is present (for CI gates).")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    findings = scan(root)

    if args.json:
        sys.stdout.write(json.dumps(findings, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    elif args.count:
        print(len(findings))
    elif args.by_file:
        if not findings:
            print("no open questions.")
        else:
            counts: dict[str, int] = {}
            for item in findings:
                counts[item["file"]] = counts.get(item["file"], 0) + 1
            for file, count in sorted(counts.items()):
                print(f"{count:3}  {file}")
            print(f"\ntotal: {len(findings)} across {len(counts)} file(s).")
    else:
        if not findings:
            print("no open questions.")
        else:
            for item in findings:
                print(f"{item['file']}:{item['line']} | {item['question']}")
            print(f"\n{len(findings)} open question(s).")

    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
