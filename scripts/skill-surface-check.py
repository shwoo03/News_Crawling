#!/usr/bin/env python3
"""Check canonical skill surfaces and generated Codex/Claude parity."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)


@dataclass
class Finding:
    severity: str
    check: str
    path: str
    detail: str


@dataclass
class SkillSurfaceResult:
    root: str
    summary: dict[str, int]
    active_skills: int
    candidate_skills: int
    meta_skills: int
    codex_skills: int
    claude_skills: int
    parity_ok: bool
    findings: list[dict[str, object]]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def skill_dirs(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir())


def parse_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, object] = {}
    current_list: list[str] | None = None
    current_key: str | None = None
    for raw in match.group(1).splitlines():
        if not raw.strip():
            continue
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("- ") and current_list is not None:
            current_list.append(stripped[2:].strip().strip("'\""))
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            current_list = []
            fields[key] = current_list
            current_key = key
            continue
        fields[key] = value.strip("'\"")
        current_list = None
        current_key = None
    return fields


def generated_names(root: Path, rel_path: str) -> set[str]:
    base = root / rel_path
    if not base.is_dir():
        return set()
    return {path.name for path in base.iterdir() if path.name != ".gitkeep" and not path.name.startswith(".")}


def check_skill_dir(root: Path, path: Path, expected_status: str | None, findings: list[Finding]) -> dict[str, object]:
    skill_file = path / "SKILL.md"
    if not skill_file.exists():
        findings.append(Finding("ERROR", "skill_missing", rel(skill_file, root), "skill directory has no SKILL.md"))
        return {}
    fields = parse_frontmatter(skill_file)
    if not fields:
        findings.append(Finding("ERROR", "frontmatter_missing", rel(skill_file, root), "SKILL.md has no YAML frontmatter"))
        return {}
    for field in ("name", "description"):
        if not fields.get(field):
            findings.append(Finding("ERROR", "frontmatter_field_missing", rel(skill_file, root), f"missing `{field}`"))
    if expected_status and fields.get("status") not in {expected_status, None, ""}:
        findings.append(Finding("ERROR", "skill_status_mismatch", rel(skill_file, root), f"expected status {expected_status}, got {fields.get('status')}"))
    return fields


def run_check(root: Path) -> SkillSurfaceResult:
    findings: list[Finding] = []
    active = skill_dirs(root / "skills" / "active")
    candidates = skill_dirs(root / "skills" / "_candidates")
    meta = skill_dirs(root / "skills" / "_meta")

    descriptions: dict[str, list[str]] = defaultdict(list)
    triggers: dict[str, list[str]] = defaultdict(list)
    declared_names: dict[str, list[str]] = defaultdict(list)
    for status, dirs in (("active", active), ("candidate", candidates), (None, meta)):
        for path in dirs:
            fields = check_skill_dir(root, path, status, findings)
            if not fields:
                continue
            name = str(fields.get("name") or path.name).strip()
            if name:
                declared_names[name].append(rel(path, root))
            description = str(fields.get("description") or "").strip().lower()
            if description:
                descriptions[description].append(rel(path, root))
            trigger_value = fields.get("trigger")
            if isinstance(trigger_value, list):
                for trigger in trigger_value:
                    normalized = str(trigger).strip().lower()
                    if normalized:
                        triggers[normalized].append(rel(path, root))

    for description, paths in sorted(descriptions.items()):
        if len(paths) > 1:
            findings.append(Finding("INFO", "description_overlap", ", ".join(paths), f"shared description: {description}"))
    for trigger, paths in sorted(triggers.items()):
        if len(paths) > 1:
            findings.append(Finding("INFO", "trigger_overlap", ", ".join(paths), f"shared trigger: {trigger}"))
    for name, paths in sorted(declared_names.items()):
        if len(paths) > 1:
            findings.append(Finding("ERROR", "skill_name_duplicate", ", ".join(paths), f"duplicate skill name: {name}"))

    expected = {path.name for path in active}
    codex = generated_names(root, ".codex/skills")
    claude = generated_names(root, ".claude/skills")
    parity_ok = expected == codex == claude
    if not (root / ".codex" / "skills").is_dir():
        findings.append(Finding("ERROR", "codex_skill_surface_missing", ".codex/skills", "generated Codex skills directory missing"))
    elif expected != codex:
        findings.append(Finding("ERROR", "codex_skill_parity", ".codex/skills", f"expected={sorted(expected)} actual={sorted(codex)}"))
    if not (root / ".claude" / "skills").is_dir():
        findings.append(Finding("ERROR", "claude_skill_surface_missing", ".claude/skills", "generated Claude skills directory missing"))
    elif expected != claude:
        findings.append(Finding("ERROR", "claude_skill_parity", ".claude/skills", f"expected={sorted(expected)} actual={sorted(claude)}"))

    summary = dict(Counter(finding.severity for finding in findings))
    for severity in ("ERROR", "WARN", "INFO"):
        summary.setdefault(severity, 0)
    return SkillSurfaceResult(
        root=str(root),
        summary=summary,
        active_skills=len(active),
        candidate_skills=len(candidates),
        meta_skills=len(meta),
        codex_skills=len(codex),
        claude_skills=len(claude),
        parity_ok=parity_ok,
        findings=[asdict(finding) for finding in findings],
    )


def render_text(result: SkillSurfaceResult) -> str:
    lines = [
        "Skill Surface Check",
        f"root: {result.root}",
        "summary: "
        f"error={result.summary.get('ERROR', 0)}, "
        f"warn={result.summary.get('WARN', 0)}, "
        f"info={result.summary.get('INFO', 0)}",
        f"active_skills: {result.active_skills}",
        f"candidate_skills: {result.candidate_skills}",
        f"meta_skills: {result.meta_skills}",
        f"codex_skills: {result.codex_skills}",
        f"claude_skills: {result.claude_skills}",
        f"parity_ok: {result.parity_ok}",
    ]
    for finding in result.findings:
        lines.append(f"  {finding['severity']:<5} [{finding['check']}] {finding['path']}: {finding['detail']}")
    if not result.findings:
        lines.append("  OK canonical skill surface is healthy")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors.")
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
    has_error = result.summary.get("ERROR", 0) > 0
    has_warn = result.summary.get("WARN", 0) > 0
    return 1 if has_error or (args.strict and has_warn) else 0


if __name__ == "__main__":
    raise SystemExit(main())
