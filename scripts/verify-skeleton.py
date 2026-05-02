#!/usr/bin/env python3
"""Verify that a copy of this skeleton (or the skeleton itself) is internally
consistent. Intended for quick health checks after edits or immediately after
`scripts/bootstrap/new-project.py` runs.

Exit code 0 if all checks pass; non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_catalog import load_catalog_modes_with_status, validate_catalog, validate_command_docs


# Ensure non-ASCII output (em-dash, Korean, etc.) prints cleanly on Windows
# consoles that default to cp949 / cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


CLAUDE_MD_LINE_LIMIT = 60
REQUIRED_TOP_LEVEL = ["AGENTS.md", "CLAUDE.md", "README.md"]
REQUIRED_CANONICAL_TOP_LEVEL = [
    ".gitignore",
    ".skeleton-version",
    "manifest.yaml",
    "references.yaml",
    "config/roles.yaml",
    "config/policy.yaml",
    "config/agent-team.yaml",
    "config/install-profiles.yaml",
    "mcp/servers.yaml",
    "plans/INDEX.md",
    "state/progress.md",
    "state/decisions.md",
    "state/blockers.md",
    "state/failures.jsonl",
    "state/cost-log.jsonl",
    "hooks/hooks.json",
    "skills/_templates/SKILL.template.md",
    "skills/_templates/AGENT.template.md",
    "skills/_templates/GOLDEN.template.yaml",
    "skills/_meta/project-scaffolder/SKILL.md",
    "skills/_meta/skill-creator/SKILL.md",
    "skills/_meta/research-evaluator/SKILL.md",
    "skills/_meta/replan-on-blocker/SKILL.md",
    "skills/_meta/reference-refresher/SKILL.md",
    ".github/workflows/ci.yml",
    "schemas/install-state.schema.json",
    "schemas/plugin-manifest.schema.json",
    "schemas/session-snapshot.schema.json",
    "schemas/catalog.schema.json",
    "schemas/runtime-event.schema.json",
]
# Required paths are grouped by why they are mandatory. This keeps the
# verifier from turning into an undifferentiated list and makes future slimming
# decisions safer: move paths between groups intentionally instead of deleting
# them from one large bucket.
REQUIRED_CORE_DOCS = [
    "docs/README.md",
    "docs/PROJECT_PROFILE.md",
    "docs/PROJECT_PROFILE.template.md",
    "docs/PROJECT_SPEC.template.md",
    "docs/PROJECT_OPERATING_PLAN.template.md",
    "docs/OPERATING_LOOP.md",
    "docs/SESSION_CONTINUITY.md",
    "docs/SKELETON_UPGRADE.md",
    "docs/ARCHITECTURE.md",
    "docs/GOVERNANCE.md",
    "docs/AGENT_REGISTRY.md",
    "docs/AGENT_QUICKSTART.md",
    "docs/WORKFLOW_CATALOG.md",
    "docs/NEW_PROJECT_CHECKLIST.md",
    "docs/GOLDEN_CASES_GUIDE.md",
    "docs/ROLE_MIGRATION.md",
    "docs/decisions/README.md",
    "docs/PIVOT_TRIGGERS.md",
    "docs/THREE_LAYER_MODEL.md",
    "docs/SKILL_DISTRIBUTION_MODEL.md",
    "docs/RUNTIME_EVENT_SCHEMA.md",
    "docs/plugin-manifest-notes.md",
    "docs/FEATURE_DECISION_GUIDE.md",
    "docs/DOCUMENTATION_STYLE_GUIDE.md",
    "docs/NOTION_DOCUMENTATION_RULES.md",
]
REQUIRED_REFERENCE_DOCS = [
    "docs/REFERENCE_REVIEW.template.md",
    "docs/REFERENCE_DISCOVERY_WORKFLOW.md",
    "docs/decisions/ADR-0001-reference-discovery-and-adoption.md",
    "research/reference-candidates/README.md",
    "research/reference-candidates/_template.md",
    "runtime/external-repos/README.md",
    "runtime/proposals/reference-adoption/README.md",
    "runtime/proposals/reference-adoption/_template.md",
]
REQUIRED_RUNTIME_DOCS = [
    "docs/RUNTIME_STARTUP.template.md",
    "runtime/state/session-handoff.md",
    "runtime/activity-log.jsonl",
    "runtime/install-state.jsonl",
    "runtime/skill-usage.jsonl",
    "runtime/skill-lifecycle.jsonl",
    "runtime/session-snapshot.json",
    "runtime/review-queue.jsonl",
    "runtime/reference-tasks.jsonl",
    "runtime/checkpoints.jsonl",
]
REQUIRED_WIKI_DOCS = [
    "docs/wiki-ops/wiki-query.md",
    "docs/wiki-ops/wiki-lint.md",
    "knowledge/index.md",
]
REQUIRED_RULE_DOCS = [
    "rules/common/README.md",
    "rules/common/search-first.md",
    "rules/common/tdd-workflow.md",
    "rules/common/verification-loop.md",
    "rules/common/security-review.md",
    "rules/common/mcp-discipline.md",
    "rules/common/code-style.md",
    "rules/common/directory-layout.md",
    "rules/common/ephemeral-files.md",
    "rules/languages/README.md",
    "rules/languages/python/README.md",
    "rules/languages/typescript/README.md",
    "examples/README.md",
]
REQUIRED_SCRIPT_PATHS = [
    "scripts/catalog.yaml",
    "scripts/lib_catalog.py",
    "scripts/lib_runtime_lock.py",
    "scripts/redact.py",
    "scripts/subdir-hints.py",
    "scripts/change-drift-check.py",
    "scripts/agent-flow.py",
    "scripts/install-state.py",
    "scripts/skill-lifecycle.py",
    "scripts/eval-all.py",
    "scripts/cost-log.py",
    "scripts/session-snapshot.py",
    "scripts/reference-intake.py",
    "scripts/reference-task-queue.py",
    "scripts/session-recall.py",
    "scripts/portability-scan.py",
    "scripts/knowledge-search.py",
    "scripts/agent-brief.py",
    "scripts/checkpoint.py",
    "scripts/tool-health.py",
    "scripts/tool-guardrail.py",
    "scripts/mcp-audit.py",
    "scripts/permission-evaluate.py",
    "scripts/path-safety.py",
    "scripts/install-profiles.py",
    "scripts/skill-stocktake.py",
    "scripts/plugin-manifest-check.py",
    "scripts/schema-check.py",
    "scripts/markdown-sanitize.py",
    "scripts/failure-classify.py",
]
REQUIRED_DOCS = (
    REQUIRED_CORE_DOCS
    + REQUIRED_REFERENCE_DOCS
    + REQUIRED_RUNTIME_DOCS
    + REQUIRED_WIKI_DOCS
    + REQUIRED_RULE_DOCS
    + REQUIRED_SCRIPT_PATHS
)
REQUIRED_RUNTIME_DIRS = [
    "runtime/state",
    "runtime/external-repos",
    "runtime/proposals",
    "runtime/validation",
    "runtime/schedules",
    "skills/active",
    "skills/_candidates",
    "skills/_deprecated",
    "agents",
    "plans/active",
    "plans/done",
    "plans/failed",
]
REMOVED_PATHS = [
    "runtime/memory",
    "codex/agents/memory-curator.md",
    "knowledge/workflows/wiki-ingest.md",
]
# Recovery hints for well-known required paths. Keeps error messages
# actionable: "missing X" alone tells an operator *what* but not *how to fix*.
# Unlisted paths fall back to a generic "restore from skeleton" hint so we do
# not silently degrade when new required paths are added.
RECOVERY_HINTS = {
    "runtime/state/session-handoff.md": (
        "run scripts/bootstrap/new-project.py into this tree, or copy the "
        "template body from docs/SESSION_CONTINUITY.md"
    ),
    "runtime/activity-log.jsonl": (
        "create an empty file: `touch runtime/activity-log.jsonl`. "
        "The post-tool-use hook will populate it on the next tool call."
    ),
    "runtime/review-queue.jsonl": (
        "create an empty file: `touch runtime/review-queue.jsonl`. "
        "scripts/review-queue.py will append decision events when needed."
    ),
    "knowledge/index.md": (
        "bootstrap re-seeds this; otherwise copy the starter table from "
        "docs/wiki-ops/wiki-lint.md"
    ),
    "docs/PROJECT_PROFILE.template.md": (
        "restore from the skeleton; this file is the single source of truth "
        "for the profile schema"
    ),
    "docs/REFERENCE_REVIEW.template.md": (
        "restore from the skeleton; new projects use this to record which "
        "external references were adopted, adapted, deferred, or rejected"
    ),
    "docs/RUNTIME_STARTUP.template.md": (
        "restore from the skeleton; new projects use this to record startup "
        "commands, env, ports, healthchecks, and failure signals"
    ),
    "CLAUDE.md": "restore from the skeleton root; see docs/SKELETON_UPGRADE.md",
    "AGENTS.md": "restore from the skeleton root; see docs/SKELETON_UPGRADE.md",
}
FRONTMATTER_PATTERN = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
AGENT_REQUIRED_FIELDS = ["name", "description"]
CLARIFICATION_OK = re.compile(r"\[NEEDS CLARIFICATION:\s*\S[^\]]*\]")
CLARIFICATION_BARE = re.compile(r"\[NEEDS CLARIFICATION(?:\s*:\s*)?\]")
CLARIFICATION_SEARCH_DIRS = ["docs"]
CLARIFICATION_SKIP_NAMES = {
    "PROJECT_PROFILE.template.md",
    "PROJECT_SPEC.template.md",
    "README.md",
    "OPERATING_LOOP.md",
}


@dataclass
class Finding:
    level: str  # "error", "warn", or "info"
    check: str
    detail: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check_claude_md_size(root: Path, findings: list[Finding]) -> None:
    path = root / "CLAUDE.md"
    if not path.exists():
        findings.append(Finding("error", "claude_md_size", "CLAUDE.md missing"))
        return
    if path.is_symlink():
        try:
            if path.resolve() == (root / "AGENTS.md").resolve():
                return
        except OSError:
            pass
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > CLAUDE_MD_LINE_LIMIT:
        findings.append(
            Finding(
                "error",
                "claude_md_size",
                f"CLAUDE.md is {len(lines)} lines; target is <= {CLAUDE_MD_LINE_LIMIT}",
            )
        )


def _with_hint(rel: str, base_msg: str) -> str:
    hint = RECOVERY_HINTS.get(rel)
    if hint:
        return f"{base_msg} -- fix: {hint}"
    # Generic fallback: point at the upgrade doc so the operator knows where
    # to look even for paths we have not hand-hinted.
    return f"{base_msg} -- fix: restore from the skeleton (see docs/SKELETON_UPGRADE.md)"


def check_required_paths(root: Path, findings: list[Finding]) -> None:
    for rel in REQUIRED_TOP_LEVEL + REQUIRED_CANONICAL_TOP_LEVEL + REQUIRED_DOCS:
        if not (root / rel).exists():
            findings.append(
                Finding(
                    "error",
                    "required_path_missing",
                    _with_hint(rel, f"missing {rel}"),
                )
            )
    for rel in REQUIRED_RUNTIME_DIRS:
        if not (root / rel).is_dir():
            findings.append(
                Finding(
                    "error",
                    "required_dir_missing",
                    _with_hint(rel, f"missing directory {rel}"),
                )
            )


def check_project_profile_nonempty(root: Path, findings: list[Finding]) -> None:
    """Warn when docs/PROJECT_PROFILE.md exists but is zero bytes.

    The cold-start protocol (CLAUDE.md / docs/SESSION_CONTINUITY.md) distinguishes
    "missing" from "empty fields". An existing-but-0-byte profile is a third state:
    the file exists so cold-start does not re-seed it, but there is nothing to read.
    Surface it as a warning so the agent or operator re-seeds from the template.
    """
    path = root / "docs" / "PROJECT_PROFILE.md"
    if not path.exists():
        return
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size == 0:
        findings.append(
            Finding(
                "warn",
                "project_profile_empty",
                "docs/PROJECT_PROFILE.md exists but is 0 bytes; "
                "re-seed from docs/PROJECT_PROFILE.template.md or run bootstrap",
            )
        )


def check_ephemeral_artifacts(root: Path, findings: list[Finding]) -> None:
    warning_patterns = (
        ("pycache_present", "**/__pycache__"),
        ("smoke_artifact_present", "runtime/*-smoke-*"),
        ("bom_lock_present", "runtime/.skeleton-bom-*.rotation.lock"),
    )
    for check_name, pattern in warning_patterns:
        matches = sorted(path for path in root.glob(pattern) if path.exists())
        for path in matches[:10]:
            findings.append(
                Finding(
                    "warn",
                    check_name,
                    f"{path.relative_to(root).as_posix()} is a temporary/test artifact; remove before publishing",
                )
            )
        if len(matches) > 10:
            findings.append(
                Finding(
                    "warn",
                    check_name,
                    f"{len(matches) - 10} more {pattern} artifact(s) not shown",
                )
            )


def check_removed_paths(root: Path, findings: list[Finding]) -> None:
    for rel in REMOVED_PATHS:
        if (root / rel).exists():
            findings.append(
                Finding(
                    "error",
                    "removed_path_present",
                    f"{rel} should not exist; it was removed from the skeleton",
                )
            )


def check_agent_frontmatter(root: Path, findings: list[Finding]) -> None:
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        findings.append(Finding("error", "agents_dir_missing", "agents/ missing"))
        return
    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.name == "README.md":
            continue
        text = agent_file.read_text(encoding="utf-8")
        match = FRONTMATTER_PATTERN.match(text)
        if not match:
            findings.append(
                Finding(
                    "error",
                    "agent_frontmatter_missing",
                    f"{agent_file.relative_to(root).as_posix()} has no YAML frontmatter",
                )
            )
            continue
        body = match.group(1)
        for field in AGENT_REQUIRED_FIELDS:
            if not re.search(rf"^{re.escape(field)}\s*:", body, re.MULTILINE):
                findings.append(
                    Finding(
                        "error",
                        "agent_field_missing",
                        f"{agent_file.relative_to(root).as_posix()} missing '{field}' in frontmatter",
                    )
                )


def check_activity_log_parses(root: Path, findings: list[Finding]) -> None:
    path = root / "runtime" / "activity-log.jsonl"
    if not path.exists():
        return
    # utf-8-sig transparently strips a leading UTF-8 BOM (which Windows editors
    # like Notepad can introduce). Plain utf-8 leaves the BOM in the stream and
    # json.loads rejects it on line 1 with "Unexpected UTF-8 BOM".
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError as exc:
            findings.append(
                Finding(
                    "error",
                    "activity_log_parse",
                    f"runtime/activity-log.jsonl:{line_no} invalid JSON: {exc}",
                )
            )


def check_agent_runs_parses(root: Path, findings: list[Finding]) -> None:
    path = root / "runtime" / "agent-runs.jsonl"
    if not path.exists():
        return
    # Same BOM-tolerance rationale as check_activity_log_parses.
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError as exc:
            findings.append(
                Finding(
                    "error",
                    "agent_runs_parse",
                    f"runtime/agent-runs.jsonl:{line_no} invalid JSON: {exc}",
                )
            )


def check_review_queue_parses(root: Path, findings: list[Finding]) -> None:
    path = root / "runtime" / "review-queue.jsonl"
    if not path.exists():
        return
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            findings.append(
                Finding(
                    "error",
                    "review_queue_parse",
                    f"runtime/review-queue.jsonl:{line_no} invalid JSON: {exc}",
                )
            )
            continue
        if not isinstance(value, dict):
            findings.append(
                Finding(
                    "error",
                    "review_queue_parse",
                    f"runtime/review-queue.jsonl:{line_no} JSONL event must be an object",
                )
            )


def check_runtime_jsonl_parses(root: Path, rel: str, check_name: str, findings: list[Finding]) -> None:
    path = root / rel
    if not path.exists():
        return
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            findings.append(Finding("error", check_name, f"{rel}:{line_no} invalid JSON: {exc}"))
            continue
        if not isinstance(value, dict):
            findings.append(Finding("error", check_name, f"{rel}:{line_no} JSONL event must be an object"))


def check_session_snapshot_parses(root: Path, findings: list[Finding]) -> None:
    path = root / "runtime" / "session-snapshot.json"
    if not path.exists():
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        findings.append(Finding("error", "session_snapshot_parse", f"runtime/session-snapshot.json invalid JSON: {exc}"))
        return
    if not isinstance(value, dict):
        findings.append(Finding("error", "session_snapshot_parse", "runtime/session-snapshot.json must contain an object"))


CATALOG_PATH_RE = re.compile(r"^\s*-?\s*path:\s*(scripts/[A-Za-z0-9_./-]+)\s*$", re.MULTILINE)
TOP_LEVEL_YAML_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*$", re.MULTILINE)
CATALOG_REQUIRED_ROUTING_MODES = ("decide", "research", "closeout", "maintain", "build")
CATALOG_REQUIRED_MODE_FIELDS = ("reason", "confidence", "requires_confirmation", "write_policy", "signal", "next_command", "suggested_questions")
CATALOG_WRITE_POLICIES = {"read_only", "manual_work_required", "write_with_confirmation"}
PERMISSION_ACTIONS = {"ask", "allow", "deny"}
PERMISSION_DECISIONS = {"allow_once", "allow_session", "deny"}


def _catalog_public_block(text: str) -> str:
    match = re.search(r"^public:\s*$", text, re.MULTILINE)
    if not match:
        return ""
    tail = text[match.end() :]
    next_key = TOP_LEVEL_YAML_KEY_RE.search(tail)
    return tail[: next_key.start()] if next_key else tail


def _catalog_routing_block(text: str) -> str:
    match = re.search(r"^routing:\s*$", text, re.MULTILINE)
    if not match:
        return ""
    tail = text[match.end() :]
    next_key = TOP_LEVEL_YAML_KEY_RE.search(tail)
    return tail[: next_key.start()] if next_key else tail


def _catalog_mode_block(routing_text: str, mode: str) -> str:
    match = re.search(rf"^\s{{4}}{re.escape(mode)}:\s*$", routing_text, re.MULTILINE)
    if not match:
        return ""
    tail = routing_text[match.end() :]
    next_mode = re.search(r"^\s{4}[A-Za-z_][A-Za-z0-9_-]*:\s*$", tail, re.MULTILINE)
    return tail[: next_mode.start()] if next_mode else tail


def check_catalog_routing(text: str, findings: list[Finding]) -> None:
    routing = _catalog_routing_block(text)
    if not routing:
        findings.append(
            Finding(
                "error",
                "script_catalog_invalid",
                "scripts/catalog.yaml must define routing.modes for agent-flow start",
            )
        )
        return
    for mode in CATALOG_REQUIRED_ROUTING_MODES:
        block = _catalog_mode_block(routing, mode)
        if not block:
            findings.append(
                Finding(
                    "error",
                    "script_catalog_invalid",
                    f"scripts/catalog.yaml routing.modes missing `{mode}`",
                )
            )
            continue
        missing = [field for field in CATALOG_REQUIRED_MODE_FIELDS if not re.search(rf"^\s{{6}}{field}:\s*", block, re.MULTILINE)]
        if mode != "build" and not re.search(r"^\s{6}goal_pattern:\s*", block, re.MULTILINE) and mode != "decide":
            missing.append("goal_pattern")
        if missing:
            findings.append(
                Finding(
                    "error",
                    "script_catalog_invalid",
                    f"scripts/catalog.yaml routing.modes.{mode} missing: {', '.join(missing)}",
                )
            )
        match = re.search(r"^\s{6}write_policy:\s*(\S+)\s*$", block, re.MULTILINE)
        if match and match.group(1).strip() not in CATALOG_WRITE_POLICIES:
            findings.append(
                Finding(
                    "error",
                    "script_catalog_invalid",
                    f"scripts/catalog.yaml routing.modes.{mode} has invalid write_policy: {match.group(1).strip()}",
                )
            )
        requires_match = re.search(r"^\s{6}requires_confirmation:\s*(\S+)\s*$", block, re.MULTILINE)
        if match and match.group(1).strip() == "write_with_confirmation":
            requires_value = requires_match.group(1).strip().lower() if requires_match else ""
            if requires_value != "true":
                findings.append(
                    Finding(
                        "error",
                        "script_catalog_invalid",
                        f"scripts/catalog.yaml routing.modes.{mode} write_with_confirmation requires requires_confirmation: true",
                    )
                )
        next_command_match = re.search(r"^\s{6}next_command:\s*(.+)$", block, re.MULTILINE)
        if next_command_match:
            command = next_command_match.group(1)
            policy = match.group(1).strip() if match else ""
            writes = any(marker in command for marker in ("--write-card", "--record", "--apply"))
            writes = writes or ("agent-flow.py research" in command and "--proposal" in command)
            if writes and policy != "write_with_confirmation":
                findings.append(
                    Finding(
                        "error",
                        "script_catalog_invalid",
                        f"scripts/catalog.yaml routing.modes.{mode} write command requires write_policy write_with_confirmation",
                    )
                )


def check_script_catalog(root: Path, findings: list[Finding]) -> None:
    for detail in validate_catalog(root):
        findings.append(Finding("error", "script_catalog_invalid", detail))
    modes, _status = load_catalog_modes_with_status(root, {}, CATALOG_REQUIRED_ROUTING_MODES)
    for detail in validate_command_docs(root, modes=modes):
        findings.append(Finding("warn", "command_metadata_invalid", detail))


def check_portability_scan(root: Path, findings: list[Finding]) -> None:
    script = root / "scripts" / "portability-scan.py"
    if not script.exists():
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(root), "--format", "json"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        findings.append(Finding("warn", "portability_scan_run", f"portability-scan failed to run: {exc}"))
        return
    if result.returncode != 0:
        findings.append(Finding("warn", "portability_scan_run", result.stderr.strip() or result.stdout.strip()))
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        findings.append(Finding("warn", "portability_scan_output", "portability-scan did not return JSON"))
        return
    count = int(payload.get("count", 0)) if isinstance(payload, dict) else 0
    if count:
        findings.append(Finding("warn", "portability_scan", f"{count} machine-specific path finding(s); run scripts/portability-scan.py"))


def _yaml_section(text: str, section: str) -> str:
    match = re.search(rf"^{re.escape(section)}:\s*$", text, re.MULTILINE)
    if not match:
        return ""
    tail = text[match.end() :]
    next_key = TOP_LEVEL_YAML_KEY_RE.search(tail)
    return tail[: next_key.start()] if next_key else tail


def _section_scalar(section: str, key: str) -> str:
    match = re.search(rf"^\s{{2}}{re.escape(key)}:\s*([^\n#]+)", section, re.MULTILINE)
    return match.group(1).strip().strip('"').strip("'") if match else ""


def _inline_list(value: str) -> list[str]:
    stripped = value.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return []
    return [item.strip().strip('"').strip("'") for item in stripped[1:-1].split(",") if item.strip()]


def check_permission_policy(root: Path, findings: list[Finding]) -> None:
    path = root / "config" / "policy.yaml"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    section = _yaml_section(text, "permissions")
    if not section:
        findings.append(Finding("error", "permission_policy_invalid", "config/policy.yaml missing permissions section"))
        return
    default_action = _section_scalar(section, "default_action")
    timeout_action = _section_scalar(section, "timeout_action")
    if default_action not in PERMISSION_ACTIONS:
        findings.append(Finding("error", "permission_policy_invalid", "permissions.default_action must be ask, allow, or deny"))
    if timeout_action != "deny":
        findings.append(Finding("error", "permission_policy_invalid", "permissions.timeout_action must be deny"))
    decisions = _inline_list(_section_scalar(section, "decision_values"))
    if not decisions:
        findings.append(Finding("error", "permission_policy_invalid", "permissions.decision_values must be an inline list"))
    else:
        invalid = [item for item in decisions if item not in PERMISSION_DECISIONS]
        missing = sorted(PERMISSION_DECISIONS.difference(decisions))
        if invalid:
            findings.append(Finding("error", "permission_policy_invalid", "invalid permission decision value(s): " + ", ".join(invalid)))
        if missing:
            findings.append(Finding("error", "permission_policy_invalid", "missing permission decision value(s): " + ", ".join(missing)))
    rule_blocks = re.finditer(r"^\s{4}-\s+id:\s*([^\n#]+)(.*?)(?=^\s{4}-\s+id:|\Z)", section, re.MULTILINE | re.DOTALL)
    for match in rule_blocks:
        rule_id = match.group(1).strip().strip('"').strip("'")
        block = match.group(2)
        action_match = re.search(r"^\s{6}action:\s*([^\n#]+)", block, re.MULTILINE)
        target_match = re.search(r"^\s{6}match:\s*([^\n#]+)", block, re.MULTILINE)
        action = action_match.group(1).strip().strip('"').strip("'") if action_match else ""
        target = target_match.group(1).strip().strip('"').strip("'") if target_match else ""
        if action not in PERMISSION_ACTIONS:
            findings.append(Finding("error", "permission_policy_invalid", f"permissions.rules.{rule_id} action must be ask, allow, or deny"))
        if target.lower() in {"shell:*", "bash:*"} and action == "allow":
            findings.append(Finding("error", "permission_policy_invalid", f"permissions.rules.{rule_id} must not allow wildcard shell execution"))
    evaluator = root / "scripts" / "permission-evaluate.py"
    if evaluator.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(evaluator), "--root", str(root), "--format", "json", "evaluate", "--action", "shell", "--resource", "*"],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        except subprocess.SubprocessError as exc:
            findings.append(Finding("error", "permission_evaluator_run", f"permission-evaluate failed to run: {exc}"))
            return
        if result.returncode != 0:
            findings.append(Finding("error", "permission_evaluator_run", result.stderr.strip() or result.stdout.strip()))
            return
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            findings.append(Finding("error", "permission_evaluator_output", "permission-evaluate did not return JSON"))
            return
        if payload.get("decision") != "deny":
            findings.append(Finding("error", "permission_evaluator_output", "shell wildcard permission must evaluate to deny"))


def check_external_validators(root: Path, findings: list[Finding]) -> None:
    commands = [
        ("plugin_manifest", "plugin-manifest-check.py", ["check"]),
        ("schema_check", "schema-check.py", ["check"]),
        ("markdown_sanitize", "markdown-sanitize.py", ["--check"]),
        ("mcp_audit", "mcp-audit.py", ["check"]),
        ("tool_health", "tool-health.py", ["check"]),
        ("tool_guardrail", "tool-guardrail.py", ["check"]),
        ("path_safety", "path-safety.py", ["check", "--path", "scripts/agent-flow.py", "--operation", "write"]),
        ("install_profiles", "install-profiles.py", ["check"]),
        ("skill_stocktake", "skill-stocktake.py", ["report"]),
    ]
    for check_name, script_name, args in commands:
        script = root / "scripts" / script_name
        if not script.exists():
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(script), "--root", str(root), "--format", "json", *args],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        except subprocess.SubprocessError as exc:
            findings.append(Finding("warn", f"{check_name}_run", f"{script_name} failed to run: {exc}"))
            continue
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            findings.append(Finding("error", f"{check_name}_invalid", detail or f"{script_name} exited {result.returncode}"))
            continue
        if check_name == "markdown_sanitize":
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                findings.append(Finding("warn", "markdown_sanitize_output", "markdown-sanitize did not return JSON"))
                continue
            count = len(payload.get("findings") or []) if isinstance(payload, dict) else 0
            if count:
                findings.append(
                    Finding(
                        "warn",
                        "markdown_sanitize_needed",
                        f"{count} Markdown file(s) need conservative sanitizer cleanup",
                    )
                )


def _marker_inside_backticks(line: str, marker_start: int) -> bool:
    """True when the marker at marker_start is inside a backtick-fenced span.

    Backticked markers are documentation examples, not outstanding questions,
    so they must not be counted. We approximate fencing by counting backticks
    preceding the marker: an odd count means we are inside a span.
    """
    return line[:marker_start].count("`") % 2 == 1


def check_clarifications(root: Path, findings: list[Finding]) -> None:
    """Surface outstanding [NEEDS CLARIFICATION: ...] markers as info and flag
    malformed bare [NEEDS CLARIFICATION] markers as warnings.

    Template files are skipped so their example text is not reported. Markers
    inside backtick fences (both inline single-backtick spans and triple-
    backtick fenced code blocks) are also skipped because they are
    documentation examples, not real pending questions. An instantiated
    PROJECT_PROFILE.md (no .template suffix) is still scanned.
    """
    open_count = 0
    malformed_examples: list[str] = []
    open_examples: list[str] = []
    for search_rel in CLARIFICATION_SEARCH_DIRS:
        search_dir = root / search_rel
        if not search_dir.is_dir():
            continue
        for path in search_dir.rglob("*.md"):
            if path.name in CLARIFICATION_SKIP_NAMES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            # Track triple-backtick fenced blocks across lines. A line whose
            # leading non-whitespace token is ``` toggles the fence; markers
            # inside the fence are documentation and must not be flagged.
            in_fence = False
            for line_no, line in enumerate(text.splitlines(), start=1):
                if line.lstrip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if "NEEDS CLARIFICATION" not in line:
                    continue
                marker_pos = line.find("[NEEDS CLARIFICATION")
                if marker_pos == -1:
                    continue
                if in_fence:
                    continue
                if _marker_inside_backticks(line, marker_pos):
                    continue
                rel = path.relative_to(root).as_posix()
                location = f"{rel}:{line_no}"
                ok = CLARIFICATION_OK.search(line)
                bare = CLARIFICATION_BARE.search(line)
                if ok:
                    open_count += 1
                    if len(open_examples) < 5:
                        open_examples.append(f"{location} {line.strip()}")
                elif bare:
                    malformed_examples.append(
                        f"{location} bare marker without question"
                    )
    for item in malformed_examples:
        findings.append(Finding("warn", "clarification_malformed", item))
    if open_count:
        findings.append(
            Finding(
                "info",
                "clarification_open",
                f"{open_count} outstanding `[NEEDS CLARIFICATION: ...]` marker(s)",
            )
        )
        for example in open_examples:
            findings.append(Finding("info", "clarification_open", example))


def check_scripts_compile(root: Path, findings: list[Finding]) -> None:
    """Parse every *.py under scripts/ so syntax errors surface here rather
    than at first runtime invocation. Cheap (no imports executed) and catches
    the common "edit a hook, ship the typo" class of regression without
    creating __pycache__ artifacts.
    """
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        return
    for path in sorted(scripts_dir.rglob("*.py")):
        try:
            with tokenize.open(path) as handle:
                source = handle.read()
            compile(source, str(path), "exec")
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            rel = path.relative_to(root).as_posix()
            detail = str(exc).strip()
            findings.append(
                Finding("error", "script_compile", f"{rel}: {detail}")
            )


def check_wiki_lint(root: Path, findings: list[Finding]) -> None:
    script = root / "scripts" / "wiki-lint.py"
    if not script.exists():
        findings.append(
            Finding("warn", "wiki_lint_missing", "scripts/wiki-lint.py missing")
        )
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--stale-days", "180"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.SubprocessError as exc:
        findings.append(
            Finding("error", "wiki_lint_run", f"wiki-lint failed to run: {exc}")
        )
        return
    stdout = result.stdout
    if result.returncode != 0:
        # Report the crash and do not trust the stdout as a valid report.
        # Parsing a malformed report would either hide the real error or
        # produce misleading "missing" findings.
        findings.append(
            Finding(
                "error",
                "wiki_lint_exit",
                f"wiki-lint exited {result.returncode}: {result.stderr.strip()}",
            )
        )
        return
    for section in (
        "stale",
        "duplicate_topic",
        "source_pointer_missing",
        "supersession_missing",
        "supersession_invalid",
        "orphan",
        "invalid",
    ):
        block = _extract_section(stdout, section)
        if block is None:
            continue
        for item in block:
            findings.append(
                Finding("error", f"wiki_{section}", item)
            )


def check_reference_candidates(root: Path, findings: list[Finding]) -> None:
    script = root / "scripts" / "validate-reference-candidates.py"
    if not script.exists():
        findings.append(
            Finding(
                "warn",
                "reference_candidate_validator_missing",
                "scripts/validate-reference-candidates.py missing",
            )
        )
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(root)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.SubprocessError as exc:
        findings.append(
            Finding(
                "error",
                "reference_candidate_validator_run",
                f"validate-reference-candidates failed to run: {exc}",
            )
        )
        return
    if result.returncode != 0:
        detail = (result.stdout or result.stderr).strip()
        findings.append(
            Finding(
                "error",
                "reference_candidate_validator_exit",
                detail or f"validate-reference-candidates exited {result.returncode}",
            )
        )


def check_reference_proposals(root: Path, findings: list[Finding]) -> None:
    script = root / "scripts" / "validate-reference-proposals.py"
    if not script.exists():
        findings.append(
            Finding(
                "warn",
                "reference_proposal_validator_missing",
                "scripts/validate-reference-proposals.py missing",
            )
        )
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(root)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.SubprocessError as exc:
        findings.append(
            Finding(
                "error",
                "reference_proposal_validator_run",
                f"validate-reference-proposals failed to run: {exc}",
            )
        )
        return
    if result.returncode != 0:
        detail = (result.stdout or result.stderr).strip()
        findings.append(
            Finding(
                "error",
                "reference_proposal_validator_exit",
                detail or f"validate-reference-proposals exited {result.returncode}",
            )
        )


def _extract_section(report: str, section: str) -> list[str] | None:
    lines = report.splitlines()
    header = f"## {section}"
    try:
        start = lines.index(header)
    except ValueError:
        return None
    items: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if stripped == "- none" or not stripped.startswith("- "):
            continue
        items.append(stripped[2:])
    return items


def render(findings: list[Finding]) -> str:
    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    infos = [f for f in findings if f.level == "info"]
    if not errors and not warns and not infos:
        return "skeleton OK: all checks passed"
    if not errors and not warns:
        lines = ["skeleton OK: all checks passed"]
    else:
        lines = ["skeleton findings:"]
        for finding in errors:
            lines.append(f"  ERROR [{finding.check}] {finding.detail}")
        for finding in warns:
            lines.append(f"  WARN  [{finding.check}] {finding.detail}")
    for finding in infos:
        lines.append(f"  INFO  [{finding.check}] {finding.detail}")
    lines.append(
        f"total: {len(errors)} error(s), {len(warns)} warning(s), "
        f"{len(infos)} info"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=None,
        help="Skeleton or project root (defaults to this script's repo root).",
    )
    parser.add_argument(
        "--skip-wiki-lint",
        action="store_true",
        help="Skip running scripts/wiki-lint.py (useful for fast checks).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    check_claude_md_size(root, findings)
    check_required_paths(root, findings)
    check_project_profile_nonempty(root, findings)
    check_ephemeral_artifacts(root, findings)
    check_removed_paths(root, findings)
    check_agent_frontmatter(root, findings)
    check_activity_log_parses(root, findings)
    check_agent_runs_parses(root, findings)
    check_review_queue_parses(root, findings)
    check_runtime_jsonl_parses(root, "runtime/install-state.jsonl", "install_state_parse", findings)
    check_runtime_jsonl_parses(root, "runtime/skill-usage.jsonl", "skill_usage_parse", findings)
    check_runtime_jsonl_parses(root, "runtime/skill-lifecycle.jsonl", "skill_lifecycle_parse", findings)
    check_runtime_jsonl_parses(root, "state/cost-log.jsonl", "cost_log_parse", findings)
    check_session_snapshot_parses(root, findings)
    check_script_catalog(root, findings)
    check_portability_scan(root, findings)
    check_permission_policy(root, findings)
    check_external_validators(root, findings)
    check_scripts_compile(root, findings)
    check_clarifications(root, findings)
    check_reference_candidates(root, findings)
    check_reference_proposals(root, findings)
    if not args.skip_wiki_lint:
        check_wiki_lint(root, findings)

    print(render(findings))
    errors = [f for f in findings if f.level == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
