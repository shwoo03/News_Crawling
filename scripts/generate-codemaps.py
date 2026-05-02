#!/usr/bin/env python3
"""Generate lightweight codemaps for agent navigation.

The codemap is intentionally read-only analysis output. It helps agents find
the right project surface without re-scanning the whole repository every turn.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SKIP_DIRS = {
    ".git",
    ".claude",
    ".codex",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "coverage",
    "runtime/external-repos",
    "docs/CODEMAPS",
}
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".sh", ".txt", ".toml"}
AREA_PREFIXES = {
    "scripts": ("scripts/",),
    "skills": ("skills/",),
    "agents": ("agents/",),
    "runtime": ("runtime/", "state/"),
    "reference": ("references.yaml", "research/", "mcp/"),
    "docs": ("docs/", "README.md", "AGENTS.md"),
    "tests": ("tests/",),
    "rules": ("rules/", "config/", "manifest.yaml", "hooks/"),
}


@dataclass
class AreaMap:
    name: str
    files: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    line_count: int = 0


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip_dir(root: Path, path: Path) -> bool:
    value = rel(root, path) if path != root else ""
    return path.name in SKIP_DIRS or value in SKIP_DIRS or any(value.startswith(item + "/") for item in SKIP_DIRS)


def walk_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_text, dirs, names in os.walk(root):
        current = Path(current_text)
        dirs[:] = [name for name in dirs if not should_skip_dir(root, current / name)]
        for name in names:
            path = current / name
            if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"AGENTS.md", "README.md", "manifest.yaml", "references.yaml"}:
                files.append(path)
    return sorted(files)


def area_for(path: str) -> str:
    for area, prefixes in AREA_PREFIXES.items():
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes):
            return area
    return "other"


def line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def build_codemap(root: Path) -> dict[str, Any]:
    areas = {name: AreaMap(name=name) for name in [*AREA_PREFIXES.keys(), "other"]}
    for path in walk_text_files(root):
        relative = rel(root, path)
        area = areas[area_for(relative)]
        area.files.append(relative)
        area.line_count += line_count(path)
        parent = Path(relative).parent.as_posix()
        if parent != "." and parent not in area.directories:
            area.directories.append(parent)
        if path.name in {"agent-flow.py", "verify.py", "quality-gate.py", "SKILL.md", "AGENTS.md", "manifest.yaml", "references.yaml"}:
            area.entry_points.append(relative)
    for area in areas.values():
        area.directories.sort()
        area.entry_points.sort()
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "root": str(root),
        "areas": {name: asdict(area) for name, area in areas.items() if area.files},
    }


def render_area(name: str, area: dict[str, Any]) -> str:
    files = area["files"]
    directories = area["directories"]
    entry_points = area["entry_points"]
    lines = [
        f"# Codemap: {name}",
        "",
        f"- `files`: {len(files)}",
        f"- `line_count`: {area['line_count']}",
        f"- `directories`: {len(directories)}",
        "",
        "## Navigation Entry Points",
        "",
    ]
    lines.extend(f"- `{item}`" for item in (entry_points[:30] or ["none detected"]))
    lines.extend(["", "## Directories", ""])
    lines.extend(f"- `{item}`" for item in directories[:80])
    lines.extend(["", "## Files", ""])
    lines.extend(f"- `{item}`" for item in files[:160])
    if len(files) > 160:
        lines.append(f"- ... {len(files) - 160} more")
    lines.append("")
    return "\n".join(lines)


def render_index(payload: dict[str, Any]) -> str:
    lines = [
        "# Codemaps",
        "",
        f"- `generated_at`: {payload['generated_at']}",
        f"- `root`: {payload['root']}",
        "",
        "| area | files | lines | navigation entry points |",
        "| --- | ---: | ---: | --- |",
    ]
    for name, area in sorted(payload["areas"].items()):
        entries = ", ".join(f"`{item}`" for item in area["entry_points"][:3]) or "-"
        lines.append(f"| `{name}` | {len(area['files'])} | {area['line_count']} | {entries} |")
    lines.extend([
        "",
        "## Usage",
        "",
        "Agents should consult this directory before broad file searches when they need a quick map of the harness surface. Agent-callable public commands are still defined only by `scripts/catalog.yaml`.",
        "",
    ])
    return "\n".join(lines)


def write_codemap(root: Path, payload: dict[str, Any]) -> list[str]:
    output_dir = root / "docs" / "CODEMAPS"
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    index = output_dir / "INDEX.md"
    index.write_text(render_index(payload), encoding="utf-8")
    written.append(index.relative_to(root).as_posix())
    for name, area in sorted(payload["areas"].items()):
        path = output_dir / f"{name}.md"
        path.write_text(render_area(name, area), encoding="utf-8")
        written.append(path.relative_to(root).as_posix())
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--write", action="store_true", help="Write docs/CODEMAPS/*.md. Default prints a preview.")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    payload = build_codemap(root)
    written = write_codemap(root, payload) if args.write else []
    if args.format == "json":
        print(json.dumps({**payload, "written": written}, ensure_ascii=False, indent=2))
    elif args.write:
        print("written codemaps:")
        for item in written:
            print(f"  {item}")
    else:
        print(render_index(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
