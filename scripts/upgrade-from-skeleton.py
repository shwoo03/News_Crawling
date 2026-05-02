#!/usr/bin/env python3
"""Plan or apply safe upgrades from this skeleton into existing projects.

Default behavior is a dry-run. Applying with --safe-only only copies files that
are missing in the target. Existing target files with different content are
reported for review and left untouched unless --include-risky is explicitly
used.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SKIP_DIR_NAMES = {
    ".git",
    ".claude",
    ".codex",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "_meta",
    "tests",
}

SKIP_FILE_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_NAME_PREFIXES = ("tmp-", "scratch-")
SKIP_NAME_CONTAINS = ("-smoke-",)

PROJECT_STATE_EXACT = {
    ".claude/settings.local.json",
    ".claude/settings.json",
    "docs/PROJECT_PROFILE.md",
    "docs/PROJECT_SPEC.md",
    "docs/PROJECT_OPERATING_PLAN.md",
    "knowledge/index.md",
    "knowledge/log.md",
    "knowledge/project-registry.md",
    "knowledge/lint-report.md",
    "runtime/activity-log.jsonl",
    "runtime/agent-runs.jsonl",
    "runtime/review-queue.jsonl",
    "runtime/state/session-handoff.md",
}

SAFE_STATE_SEED_EXACT = {
    "runtime/review-queue.jsonl",
}

PROJECT_STATE_PREFIXES = (
    "runtime/archive/",
    "runtime/external-repos/",
    "runtime/schedules/",
    "runtime/validation/",
)

PROJECT_STATE_RUNTIME_PREFIXES = (
    "runtime/proposals/",
)

RUNTIME_TEMPLATE_ALLOWLIST = {
    "runtime/external-repos/README.md",
    "runtime/external-repos/.gitkeep",
    "runtime/proposals/reference-adoption/README.md",
    "runtime/proposals/reference-adoption/_template.md",
}

SAFE_MISSING_EXACT = {
    "scripts/quality-gate.py",
    "runtime/review-queue.jsonl",
    "scripts/review-queue.py",
    "scripts/skeleton-doctor.py",
    "scripts/upgrade-from-skeleton.py",
}

CANONICAL_PREFIXES = (
    "docs/",
    "rules/",
    "scripts/",
    "codex/",
    "examples/",
    "research/reference-candidates/",
)

CANONICAL_EXACT = {
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    ".editorconfig",
}

SAFE_MISSING_SUFFIXES = (
    ".template.md",
    "_template.md",
    "README.md",
    ".gitkeep",
)


@dataclass
class Action:
    target: str
    path: str
    action: str
    safety: str
    reason: str
    applied: bool = False


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip_source(path: Path, source: Path, target_roots: list[Path]) -> bool:
    rel = rel_posix(path, source)
    if any(path == target or is_relative_to(path, target) for target in target_roots):
        return True
    if any(part in SKIP_DIR_NAMES for part in path.relative_to(source).parts):
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if path.name.startswith(SKIP_NAME_PREFIXES):
        return True
    if any(fragment in path.name for fragment in SKIP_NAME_CONTAINS):
        return True
    if rel.startswith("runtime/.") and rel.endswith(".lock"):
        return True
    if path.is_symlink():
        return True
    if rel in SAFE_STATE_SEED_EXACT:
        return False
    if rel in PROJECT_STATE_EXACT:
        return True
    if rel in RUNTIME_TEMPLATE_ALLOWLIST:
        return False
    if rel.startswith("runtime/state/"):
        return True
    if rel.startswith(PROJECT_STATE_PREFIXES):
        return True
    if rel.startswith(PROJECT_STATE_RUNTIME_PREFIXES):
        return True
    return False


def iter_source_files(source: Path, target_roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if should_skip_source(path, source, target_roots):
            continue
        if path.is_file():
            files.append(path)
    return files


def is_canonical(rel: str) -> bool:
    return rel in CANONICAL_EXACT or rel.startswith(CANONICAL_PREFIXES) or rel in RUNTIME_TEMPLATE_ALLOWLIST


def is_safe_missing(rel: str) -> bool:
    path = Path(rel)
    return (
        rel in RUNTIME_TEMPLATE_ALLOWLIST
        or rel in SAFE_MISSING_EXACT
        or path.name.endswith(SAFE_MISSING_SUFFIXES)
    )


def classify_file(source_file: Path, source: Path, target: Path) -> Action:
    rel = rel_posix(source_file, source)
    target_file = target / rel

    if rel in PROJECT_STATE_EXACT:
        return Action(str(target), rel, "skip", "protected", "project-owned state")
    if rel in SAFE_STATE_SEED_EXACT and target_file.exists():
        return Action(str(target), rel, "skip", "protected", "project-owned state")
    if rel in RUNTIME_TEMPLATE_ALLOWLIST:
        pass
    elif rel.startswith(PROJECT_STATE_PREFIXES) or rel.startswith(PROJECT_STATE_RUNTIME_PREFIXES):
        return Action(str(target), rel, "skip", "protected", "runtime/project-owned path")
    elif not is_canonical(rel):
        return Action(str(target), rel, "review", "manual", "unclassified path")

    if not target_file.exists():
        safety = "safe" if is_safe_missing(rel) else "review"
        reason = "missing safe template/readme" if safety == "safe" else "missing canonical file"
        return Action(str(target), rel, "add", safety, reason)
    if target_file.is_dir():
        return Action(str(target), rel, "review", "manual", "target path is a directory")
    if filecmp.cmp(source_file, target_file, shallow=False):
        return Action(str(target), rel, "unchanged", "safe", "same content")
    return Action(str(target), rel, "update_available", "risky", "target has different content")


def plan_target(source: Path, target: Path, source_files: list[Path]) -> list[Action]:
    if not target.is_dir():
        return [
            Action(
                str(target),
                ".",
                "skip",
                "protected",
                "target is not a directory",
            )
        ]
    if target == source or is_relative_to(target, source):
        return [
            Action(
                str(target),
                ".",
                "skip",
                "protected",
                "target is the skeleton or inside the skeleton",
            )
        ]
    return [classify_file(path, source, target) for path in source_files]


def apply_actions(
    actions: list[Action],
    source: Path,
    *,
    safe_only: bool,
    include_risky: bool,
) -> None:
    for action in actions:
        if action.action not in {"add", "update_available"}:
            continue
        if action.safety == "safe":
            pass
        elif action.safety == "risky" and include_risky and not safe_only:
            pass
        else:
            continue
        src = source / action.path
        dst = Path(action.target) / action.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        action.applied = True


def discover_projects(root: Path) -> list[Path]:
    if not root.is_dir():
        raise SystemExit(f"--projects-root is not a directory: {root}")
    projects: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "AGENTS.md").exists() or (child / "CLAUDE.md").exists():
            projects.append(child.resolve())
    return projects


def summarize(actions: list[Action]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for action in actions:
        key = f"{action.action}:{action.safety}"
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def render_text(actions: list[Action], *, dry_run: bool) -> str:
    lines: list[str] = []
    by_target: dict[str, list[Action]] = {}
    for action in actions:
        by_target.setdefault(action.target, []).append(action)
    for target, target_actions in by_target.items():
        lines.append(f"target: {target}")
        summary = summarize(target_actions)
        for key, count in summary.items():
            lines.append(f"  {key}: {count}")
        visible = [
            a
            for a in target_actions
            if a.action in {"add", "update_available", "review", "skip"} and a.path != "."
        ]
        for action in visible[:40]:
            applied = " applied" if action.applied else ""
            lines.append(
                f"  - {action.action} [{action.safety}]{applied}: {action.path} ({action.reason})"
            )
        if len(visible) > 40:
            lines.append(f"  - ... {len(visible) - 40} more item(s)")
    lines.append("dry-run: no files changed" if dry_run else "apply: completed")
    return "\n".join(lines)


def append_upgrade_log(target: Path, actions: list[Action]) -> None:
    applied = [a for a in actions if a.applied]
    if not applied:
        return
    log = target / "runtime" / "activity-log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": utc_now(),
        "phase": "maintenance",
        "action": "skeleton_upgraded",
        "project": target.name,
        "goal_lineage": [
            "maintenance",
            target.name,
            "follow skeleton improvements",
        ],
        "tool_call": {
            "tool": "scripts/upgrade-from-skeleton.py",
            "status": "completed",
            "summary": "applied safe skeleton upgrade files",
        },
        "data": {
            "applied_paths": [a.path for a in applied],
            "mode": "safe-only",
        },
    }
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=None,
        help="Skeleton root (defaults to this script's repository root).",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Existing project root to inspect or upgrade. Can be repeated.",
    )
    parser.add_argument(
        "--projects-root",
        default=None,
        help="Directory whose immediate children should be treated as projects if they contain AGENTS.md or CLAUDE.md.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply eligible actions. Without this flag the command is dry-run only.",
    )
    parser.add_argument(
        "--safe-only",
        action="store_true",
        help="Only apply safe missing-file additions. This is the recommended apply mode.",
    )
    parser.add_argument(
        "--include-risky",
        action="store_true",
        help="Also overwrite changed canonical files. Requires --apply and is not compatible with --safe-only.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    args = parser.parse_args()

    if args.include_risky and args.safe_only:
        raise SystemExit("--include-risky cannot be combined with --safe-only")
    if args.include_risky and not args.apply:
        raise SystemExit("--include-risky requires --apply")
    if args.safe_only and not args.apply:
        raise SystemExit("--safe-only requires --apply")

    source = Path(args.source).resolve() if args.source else repo_root()
    if not source.is_dir():
        raise SystemExit(f"--source is not a directory: {source}")

    targets = [Path(item).resolve() for item in args.target]
    if args.projects_root:
        targets.extend(discover_projects(Path(args.projects_root).resolve()))
    # De-duplicate while preserving order.
    deduped: list[Path] = []
    seen: set[str] = set()
    for target in targets:
        key = str(target).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    if not deduped:
        raise SystemExit("provide --target at least once or --projects-root")

    source_files = iter_source_files(source, deduped)
    all_actions: list[Action] = []
    by_target: dict[Path, list[Action]] = {}
    for target in deduped:
        actions = plan_target(source, target, source_files)
        by_target[target] = actions
        all_actions.extend(actions)

    if args.apply:
        for target, actions in by_target.items():
            apply_actions(
                actions,
                source,
                safe_only=args.safe_only,
                include_risky=args.include_risky,
            )
            append_upgrade_log(target, actions)

    if args.json:
        payload = {
            "source": str(source),
            "dry_run": not args.apply,
            "summary": summarize(all_actions),
            "actions": [asdict(action) for action in all_actions],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(all_actions, dry_run=not args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
