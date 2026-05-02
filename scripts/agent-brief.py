#!/usr/bin/env python3
"""Create a bounded brief for specialist subagents."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from importlib import util


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SPECIALISTS = {
    "build-error-resolver": "Minimal build, typecheck, and test failure fixes after implementation.",
    "security-reviewer": "Review security-scan, permission, secret, and copied-source findings.",
    "reference-reviewer": "Compare reference candidates and produce source-backed absorption notes.",
    "docs-sync-auditor": "Check docs, catalog, codemap, and workflow drift.",
    "closeout-validator": "Independently inspect verify, quality-gate, and completion evidence.",
}
WRITE_POLICIES = {"read_only", "manual_work_required", "write_with_confirmation"}


@dataclass
class Brief:
    role: str
    goal: str
    scope: list[str]
    write_policy: str
    mission: str
    allowed_files: list[str]
    forbidden_actions: list[str]
    relevant_rules: list[str]
    recommended_checks: list[str]
    handoff_expectation: str
    subdirectory_hints: list[dict[str, str]]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def normalize_scope(root: Path, values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values or ["."]:
        path = Path(value)
        resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
        try:
            rel = resolved.relative_to(root.resolve(strict=False)).as_posix()
        except ValueError as exc:
            raise ValueError(f"scope outside root: {value}") from exc
        if rel not in result:
            result.append(rel)
    return result


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    return [item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()]


def load_team_registry(root: Path) -> dict[str, dict[str, object]]:
    path = root / "config" / "agent-team.yaml"
    if not path.exists():
        return {}
    entries: dict[str, dict[str, object]] = {}
    in_specialists = False
    current = ""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if indent == 0:
            in_specialists = stripped == "specialists:"
            current = ""
            continue
        if not in_specialists:
            continue
        if indent == 2 and stripped.endswith(":"):
            current = stripped[:-1]
            entries[current] = {}
            continue
        if current and indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            entries[current][key] = parse_inline_list(value) if value.startswith("[") else value.strip('"').strip("'")
    return entries


def recommended_checks(role: str) -> list[str]:
    if role == "security-reviewer":
        return ["python scripts/security-scan.py --root . --include-runtime --strict"]
    if role == "reference-reviewer":
        return ["python scripts/validate-reference-candidates.py --root .", "python scripts/validate-reference-proposals.py --root ."]
    if role == "docs-sync-auditor":
        return ["python scripts/generate-codemaps.py --root . --format json", "python scripts/wiki-lint.py --root . --format json"]
    if role == "closeout-validator":
        return ["python scripts/verify.py --root .", "python scripts/quality-gate.py --root . --format json"]
    return ["python -m unittest discover -s tests -v"]


def load_subdir_hints(root: Path, scope: list[str]) -> list[dict[str, str]]:
    path = root / "scripts" / "subdir-hints.py"
    if not path.exists():
        return []
    spec = util.spec_from_file_location("subdir_hints_module", path)
    if spec is None or spec.loader is None:
        return []
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hints: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in scope:
        for hint in module.collect_hints(root, item):
            key = str(hint.get("path", ""))
            if key and key not in seen:
                seen.add(key)
                hints.append(hint)
    return hints


def build_brief(root: Path, args: argparse.Namespace) -> Brief:
    registry = load_team_registry(root)
    known_roles = set(SPECIALISTS) | set(registry)
    if args.role not in known_roles:
        raise ValueError(f"unknown specialist role: {args.role}")
    configured = registry.get(args.role, {})
    write_policy = args.write_policy or str(configured.get("write_policy") or "read_only")
    if write_policy not in WRITE_POLICIES:
        raise ValueError(f"invalid write policy: {args.write_policy}")
    default_scope = configured.get("default_scope") if isinstance(configured.get("default_scope"), list) else []
    scope_values = args.scope or [str(item) for item in default_scope] or ["."]
    scope = normalize_scope(root, scope_values)
    forbidden = [
        "Do not edit files outside allowed_files.",
        "Do not run dependency install, git push, or destructive filesystem commands.",
        "Do not change public command boundaries; route through scripts/agent-flow.py.",
    ]
    if write_policy == "read_only":
        forbidden.append("Do not modify files; report findings only.")
    elif write_policy == "manual_work_required":
        forbidden.append("Do not write until the planner/user has approved the implementation scope.")
    return Brief(
        role=args.role,
        goal=args.goal.strip(),
        scope=scope,
        write_policy=write_policy,
        mission=str(configured.get("mission") or SPECIALISTS.get(args.role, "")),
        allowed_files=scope,
        forbidden_actions=forbidden,
        relevant_rules=["AGENTS.md", "scripts/catalog.yaml", "config/policy.yaml", "rules/common/confirmation-required.md"],
        recommended_checks=[str(item) for item in configured.get("recommended_checks", [])] if isinstance(configured.get("recommended_checks"), list) else recommended_checks(args.role),
        handoff_expectation="Return findings, changed files if any, checks run, residual risk, and next recommended action.",
        subdirectory_hints=load_subdir_hints(root, scope),
    )


def render_text(brief: Brief) -> str:
    lines = [
        f"Role: {brief.role}",
        f"Goal: {brief.goal}",
        f"Mission: {brief.mission}",
        f"Write policy: {brief.write_policy}",
        "Allowed files:",
        *[f"- {item}" for item in brief.allowed_files],
        "Forbidden actions:",
        *[f"- {item}" for item in brief.forbidden_actions],
        "Recommended checks:",
        *[f"- {item}" for item in brief.recommended_checks],
        "Subdirectory hints:",
        *[f"- {item['path']}: {item.get('summary', '')}" for item in brief.subdirectory_hints],
        f"Handoff: {brief.handoff_expectation}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--role", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--write-policy", choices=sorted(WRITE_POLICIES), default="")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    try:
        brief = build_brief(root, args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(asdict(brief), ensure_ascii=False, indent=2))
    else:
        print(render_text(brief))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
