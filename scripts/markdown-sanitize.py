#!/usr/bin/env python3
"""Preview or apply conservative fixes for generated Markdown wrappers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SCAN_DIRS = ("docs", "skills", "rules", "research", "agents", "plans", "runtime/proposals")
SKIP_PARTS = {".git", "__pycache__", "node_modules", "docs/CODEMAPS"}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def is_markdown_target(root: Path, path: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    rel = rel_to_root(root, path)
    return not any(part in rel for part in SKIP_PARTS)


def default_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    for rel in SCAN_DIRS:
        base = root / rel
        if base.is_dir():
            targets.extend(path for path in base.rglob("*.md") if is_markdown_target(root, path))
    for rel in ("AGENTS.md", "README.md", "SECURITY.md"):
        path = root / rel
        if path.is_file():
            targets.append(path)
    return sorted(set(targets))


def sanitize_text(text: str) -> tuple[str, list[str]]:
    fixes: list[str] = []
    out = text
    if out.startswith("\ufeff"):
        out = out.lstrip("\ufeff")
        fixes.append("strip_bom")
    stripped = out.strip()
    for fence in ("```markdown", "```md", "```"):
        if stripped.startswith(fence) and stripped.endswith("```"):
            body = stripped[len(fence) :]
            if body.startswith("\n"):
                body = body[1:]
            body = body[:-3]
            out = body.strip("\n") + "\n"
            fixes.append("unwrap_whole_document_fence")
            break
    if out.startswith("frontmatter:\n---"):
        out = out.split("\n", 1)[1]
        fixes.append("remove_frontmatter_wrapper")
    if out.startswith(" \n---") or out.startswith("\n---"):
        out = out.lstrip()
        fixes.append("trim_leading_blank_before_frontmatter")
    if out and not out.endswith("\n"):
        out += "\n"
        fixes.append("ensure_final_newline")
    return out, fixes


def inspect_file(root: Path, path: Path, apply: bool) -> dict[str, Any] | None:
    try:
        original = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return {"path": rel_to_root(root, path), "fixes": [], "error": str(exc)}
    sanitized, fixes = sanitize_text(original)
    if not fixes:
        return None
    if apply:
        path.write_text(sanitized, encoding="utf-8")
    return {"path": rel_to_root(root, path), "fixes": fixes, "applied": apply}


def render_text(payload: dict[str, Any]) -> str:
    lines = ["Markdown Sanitize", f"root: {payload['root']}", f"findings: {len(payload['findings'])}"]
    for finding in payload["findings"]:
        action = "APPLIED" if finding.get("applied") else "PREVIEW"
        lines.append(f"  {action} {finding['path']}: {', '.join(finding.get('fixes') or [])}")
    if not payload["findings"]:
        lines.append("  OK no conservative fixes needed")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--path", action="append", default=[], help="Markdown file to inspect. Repeatable.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--apply", action="store_true", help="Apply fixes. Default previews only.")
    parser.add_argument("--check", action="store_true", help="Scan default Markdown targets.")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    targets = [Path(value) for value in args.path]
    if not targets or args.check:
        targets = default_targets(root)
    resolved: list[Path] = []
    for target in targets:
        path = target if target.is_absolute() else root / target
        try:
            path.resolve(strict=False).relative_to(root.resolve(strict=False))
        except ValueError:
            print(f"path outside root: {target}", file=sys.stderr)
            return 2
        if path.is_file():
            resolved.append(path)
    findings = [item for path in resolved if (item := inspect_file(root, path, args.apply)) is not None]
    payload = {"root": str(root), "applied": args.apply, "checked": len(resolved), "findings": findings}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
