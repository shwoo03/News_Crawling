#!/usr/bin/env python3
"""Collect nearby directory instructions for scoped specialist briefs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HINT_NAMES = ("AGENTS.md", "CLAUDE.md", "README.md")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def summarize(path: Path, *, max_lines: int = 5) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return " | ".join(lines)


def collect_hints(root: Path, scope: str) -> list[dict[str, Any]]:
    base = Path(scope)
    resolved = base.resolve(strict=False) if base.is_absolute() else (root / base).resolve(strict=False)
    resolved.relative_to(root.resolve(strict=False))
    if resolved.is_file():
        resolved = resolved.parent
    hints: list[dict[str, Any]] = []
    seen: set[Path] = set()
    current = resolved
    while True:
        try:
            current.relative_to(root.resolve(strict=False))
        except ValueError:
            break
        for name in HINT_NAMES:
            path = current / name
            if path.is_file() and path not in seen:
                seen.add(path)
                hints.append({"path": rel(root, path), "kind": name, "summary": summarize(path)})
        rules_dir = current / "rules"
        if rules_dir.is_dir():
            for path in sorted(rules_dir.glob("*.md")):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    hints.append({"path": rel(root, path), "kind": "rules", "summary": summarize(path)})
        if current == root.resolve(strict=False):
            break
        current = current.parent
    return hints[:12]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--scope", default=".")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    try:
        hints = collect_hints(root, args.scope)
    except ValueError as exc:
        print(f"scope outside root: {exc}")
        return 2
    if args.format == "json":
        print(json.dumps({"hints": hints}, ensure_ascii=False, indent=2))
    else:
        if not hints:
            print("no subdirectory hints")
        for hint in hints:
            print(f"{hint['path']}: {hint['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
