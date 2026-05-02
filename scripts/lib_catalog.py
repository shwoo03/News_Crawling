#!/usr/bin/env python3
"""Shared lightweight parser and validator for scripts/catalog.yaml.

The project intentionally avoids external YAML dependencies in the skeleton
runtime. This module only parses the small catalog subset we own: top-level
sections, routing.modes scalar fields, simple lists, and path entries.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


MODES = {"decide", "research", "build", "maintain", "closeout"}
WRITE_POLICIES = {"read_only", "manual_work_required", "write_with_confirmation"}
REQUIRED_MODE_FIELDS = (
    "reason",
    "confidence",
    "requires_confirmation",
    "write_policy",
    "signal",
    "next_command",
    "suggested_questions",
)
WRITE_MARKERS = ("--write-card", "--record", "--apply")
PATH_RE = re.compile(r"^\s*-?\s*path:\s*(scripts/[A-Za-z0-9_./-]+)\s*$", re.MULTILINE)
TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*$", re.MULTILINE)
COMMAND_DOC_FIELDS = ("name", "intent", "public", "maps_to", "write_policy", "requires_confirmation")


def parse_catalog_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped in {"true", "false"}:
        return stripped == "true"
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def top_level_block(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*$", text, re.MULTILINE)
    if not match:
        return ""
    tail = text[match.end() :]
    next_key = TOP_LEVEL_KEY_RE.search(tail)
    return tail[: next_key.start()] if next_key else tail


def load_catalog_modes_with_status(
    root: Path,
    defaults: dict[str, dict[str, Any]],
    valid_modes: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    modes = {mode: dict(config) for mode, config in defaults.items()}
    valid_modes = valid_modes or MODES
    path = root / "scripts" / "catalog.yaml"
    if not path.exists():
        return modes, {"source": "defaults", "ok": False, "detail": "scripts/catalog.yaml not found"}
    current_mode = ""
    current_list = ""
    in_routing = False
    in_modes = False
    parsed_any = False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for raw in lines:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            stripped = raw.strip()
            if indent == 0:
                in_routing = stripped == "routing:"
                in_modes = False
                current_mode = ""
                current_list = ""
                continue
            if in_routing and indent == 2 and stripped == "modes:":
                in_modes = True
                continue
            if not (in_routing and in_modes):
                continue
            if indent == 4 and stripped.endswith(":"):
                mode = stripped[:-1]
                if mode in valid_modes:
                    current_mode = mode
                    current_list = ""
                    modes.setdefault(mode, {})
                    parsed_any = True
                else:
                    current_mode = ""
                    current_list = ""
                continue
            if not current_mode:
                continue
            if indent == 6 and ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value:
                    modes[current_mode][key] = parse_catalog_scalar(value)
                    current_list = ""
                else:
                    modes[current_mode][key] = []
                    current_list = key
                continue
            if indent == 8 and current_list and stripped.startswith("- "):
                target = modes[current_mode].setdefault(current_list, [])
                if isinstance(target, list):
                    target.append(parse_catalog_scalar(stripped[2:]))
    except OSError as exc:
        return modes, {"source": "defaults", "ok": False, "detail": str(exc)}
    if not parsed_any:
        return modes, {"source": "defaults", "ok": False, "detail": "routing.modes not parsed"}
    return modes, {"source": "scripts/catalog.yaml", "ok": True, "detail": "parsed"}


def validate_catalog(root: Path, *, required_modes: tuple[str, ...] = ("decide", "research", "closeout", "maintain", "build")) -> list[str]:
    path = root / "scripts" / "catalog.yaml"
    if not path.exists():
        return ["scripts/catalog.yaml missing"]
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    public_paths = PATH_RE.findall(top_level_block(text, "public"))
    if public_paths.count("scripts/agent-flow.py") != 1:
        findings.append("scripts/catalog.yaml public section must contain exactly one scripts/agent-flow.py path")
    extra_public = [item for item in public_paths if item != "scripts/agent-flow.py"]
    if extra_public:
        findings.append("scripts/catalog.yaml public section must not list internal tools: " + ", ".join(extra_public))
    future = top_level_block(text, "future_candidates")
    future_paths = set(PATH_RE.findall(future))
    for rel in PATH_RE.findall(text):
        if rel in future_paths:
            continue
        if not (root / rel).is_file():
            findings.append(f"scripts/catalog.yaml lists missing script path: {rel}")

    routing = top_level_block(text, "routing")
    if not routing:
        findings.append("scripts/catalog.yaml must define routing.modes for agent-flow start")
        return findings
    for mode in required_modes:
        block = _mode_block(routing, mode)
        if not block:
            findings.append(f"scripts/catalog.yaml routing.modes missing `{mode}`")
            continue
        missing = [field for field in REQUIRED_MODE_FIELDS if not re.search(rf"^\s{{6}}{field}:\s*", block, re.MULTILINE)]
        if mode not in {"build", "decide"} and not re.search(r"^\s{6}goal_pattern:\s*", block, re.MULTILINE):
            missing.append("goal_pattern")
        if missing:
            findings.append(f"scripts/catalog.yaml routing.modes.{mode} missing: {', '.join(missing)}")
        policy_match = re.search(r"^\s{6}write_policy:\s*(\S+)\s*$", block, re.MULTILINE)
        policy = policy_match.group(1).strip() if policy_match else ""
        if policy and policy not in WRITE_POLICIES:
            findings.append(f"scripts/catalog.yaml routing.modes.{mode} has invalid write_policy: {policy}")
        requires_match = re.search(r"^\s{6}requires_confirmation:\s*(\S+)\s*$", block, re.MULTILINE)
        requires = requires_match.group(1).strip().lower() if requires_match else ""
        if policy == "write_with_confirmation" and requires != "true":
            findings.append(f"scripts/catalog.yaml routing.modes.{mode} write_with_confirmation requires requires_confirmation: true")
        command_match = re.search(r"^\s{6}next_command:\s*(.+)$", block, re.MULTILINE)
        command = command_match.group(1) if command_match else ""
        writes = any(marker in command for marker in WRITE_MARKERS)
        writes = writes or ("agent-flow.py research" in command and "--proposal" in command)
        if writes and policy != "write_with_confirmation":
            findings.append(f"scripts/catalog.yaml routing.modes.{mode} write command requires write_policy write_with_confirmation")
    return findings


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    block = text[4:end]
    data: dict[str, str] = {}
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def validate_command_docs(root: Path, *, modes: dict[str, dict[str, Any]] | None = None) -> list[str]:
    docs = root / "docs" / "commands"
    if not docs.is_dir():
        return []
    modes = modes or {}
    findings: list[str] = []
    for path in sorted(docs.glob("*.md")):
        metadata = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        missing = [field for field in COMMAND_DOC_FIELDS if not metadata.get(field)]
        if missing:
            findings.append(f"{path.relative_to(root).as_posix()} command metadata missing: {', '.join(missing)}")
            continue
        name = metadata["name"]
        if name != path.stem:
            findings.append(f"{path.relative_to(root).as_posix()} command metadata name must match filename")
        public = metadata["public"].lower()
        if public not in {"true", "false"}:
            findings.append(f"{path.relative_to(root).as_posix()} command metadata public must be true or false")
        requires = metadata["requires_confirmation"].lower()
        if requires not in {"true", "false"}:
            findings.append(f"{path.relative_to(root).as_posix()} command metadata requires_confirmation must be true or false")
        policy = metadata["write_policy"]
        if policy not in WRITE_POLICIES:
            findings.append(f"{path.relative_to(root).as_posix()} command metadata has invalid write_policy: {policy}")
        if name in modes:
            mode = modes[name]
            expected_policy = str(mode.get("write_policy") or "")
            if expected_policy and policy != expected_policy:
                findings.append(f"{path.relative_to(root).as_posix()} write_policy differs from scripts/catalog.yaml routing.modes.{name}")
            expected_requires = str(mode.get("requires_confirmation")).lower()
            if expected_requires in {"true", "false"} and requires != expected_requires:
                findings.append(f"{path.relative_to(root).as_posix()} requires_confirmation differs from scripts/catalog.yaml routing.modes.{name}")
            maps_to = metadata["maps_to"]
            if name != "verify" and f"agent-flow.py {name}" not in maps_to and not (name == "start" and "agent-flow.py start" in maps_to):
                findings.append(f"{path.relative_to(root).as_posix()} maps_to must point at the matching agent-flow subcommand")
    return findings


def _mode_block(routing_text: str, mode: str) -> str:
    match = re.search(rf"^\s{{4}}{re.escape(mode)}:\s*$", routing_text, re.MULTILINE)
    if not match:
        return ""
    tail = routing_text[match.end() :]
    next_mode = re.search(r"^\s{4}[A-Za-z_][A-Za-z0-9_-]*:\s*$", tail, re.MULTILINE)
    return tail[: next_mode.start()] if next_mode else tail
