#!/usr/bin/env python3
"""Report qualitative stocktake recommendations for skeleton skills."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SKILL_DIRS = ("skills/active", "skills/_candidates", "skills/_meta")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    data: dict[str, Any] = {}
    current_key = ""
    for line in block.splitlines():
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            key, value = line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            if value:
                data[current_key] = value.strip('"').strip("'")
            else:
                data[current_key] = []
        elif current_key and line.strip().startswith("-"):
            value = line.strip()[1:].strip().strip('"').strip("'")
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(value)
    return data


def iter_skills(root: Path) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for rel in SKILL_DIRS:
        base = root / rel
        if not base.is_dir():
            continue
        for skill_md in sorted(base.glob("*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            meta = frontmatter(text)
            name = str(meta.get("name") or skill_md.parent.name)
            triggers = meta.get("trigger") if isinstance(meta.get("trigger"), list) else []
            goldens = list(skill_md.parent.glob("goldens/*.yaml"))
            skills.append(
                {
                    "name": name,
                    "path": skill_md.parent.relative_to(root).as_posix(),
                    "surface": rel,
                    "status": str(meta.get("status") or ("active" if rel == "skills/active" else "candidate")),
                    "triggers": triggers,
                    "goldens_count": len(goldens),
                }
            )
    return skills


def read_usage(root: Path) -> dict[str, dict[str, int]]:
    path = root / "runtime" / "skill-usage.jsonl"
    usage: dict[str, dict[str, int]] = defaultdict(lambda: {"uses": 0, "success": 0, "failure": 0})
    if not path.exists():
        return usage
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        skill = str(event.get("skill") or "")
        if not skill:
            continue
        usage[skill]["uses"] += 1
        outcome = str(event.get("outcome") or "").lower()
        if outcome == "success":
            usage[skill]["success"] += 1
        elif outcome == "failure":
            usage[skill]["failure"] += 1
    return usage


def trigger_key(trigger: str) -> str:
    return " ".join(sorted(re.findall(r"[A-Za-z0-9_가-힣-]+", trigger.lower())))


def recommendations(root: Path) -> dict[str, Any]:
    skills = iter_skills(root)
    usage = read_usage(root)
    trigger_index: dict[str, list[str]] = defaultdict(list)
    name_index: dict[str, list[str]] = defaultdict(list)
    for skill in skills:
        name_index[skill["name"]].append(skill["path"])
        for trigger in skill["triggers"]:
            key = trigger_key(str(trigger))
            if key:
                trigger_index[key].append(skill["name"])

    duplicate_names = {name for name, paths in name_index.items() if len(paths) > 1}
    duplicate_trigger_names = {name for names in trigger_index.values() if len(set(names)) > 1 for name in names}

    results: list[dict[str, Any]] = []
    for skill in skills:
        name = skill["name"]
        stats = usage.get(name, {"uses": 0, "success": 0, "failure": 0})
        uses = int(stats["uses"])
        failures = int(stats["failure"])
        successes = int(stats["success"])
        rate = round(successes / uses, 4) if uses else None
        if name in duplicate_names or name in duplicate_trigger_names:
            rec = "merge"
            reason = "duplicate skill name or overlapping trigger surface"
        elif skill["status"] == "deprecated":
            rec = "retire"
            reason = "skill is already deprecated"
        elif uses >= 3 and failures > successes:
            rec = "retire"
            reason = "failure count exceeds success count"
        elif skill["goldens_count"] == 0:
            rec = "improve"
            reason = "no golden coverage"
        elif uses == 0:
            rec = "update"
            reason = "golden-covered but unused in ledger"
        else:
            rec = "keep"
            reason = "usage or golden coverage is present"
        results.append({**skill, "uses": uses, "success_rate": rate, "recommendation": rec, "reason": reason})
    return {"skills": sorted(results, key=lambda item: (item["recommendation"], item["name"])), "count": len(results)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    payload = recommendations(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in payload["skills"]:
            print(f"{item['recommendation']:<7} {item['name']} - {item['reason']}")
        if not payload["skills"]:
            print("no skills found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
