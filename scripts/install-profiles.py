#!/usr/bin/env python3
"""Plan and validate install profiles from config/install-profiles.yaml."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


COMPONENT_RE = re.compile(r"components:\s*\[([^\]]*)\]")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def inline_list(value: str) -> list[str]:
    return [item.strip().strip('"').strip("'") for item in value.split(",") if item.strip()]


def load_profiles(root: Path) -> dict[str, Any]:
    path = root / "config" / "install-profiles.yaml"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    default_match = re.search(r"^default_profile:\s*([^\n#]+)", text, re.MULTILINE)
    default = default_match.group(1).strip().strip('"').strip("'") if default_match else ""
    profiles: dict[str, dict[str, Any]] = {}
    profile_block = re.search(r"^profiles:\s*$", text, re.MULTILINE)
    if profile_block:
        tail = text[profile_block.end() :]
        for match in re.finditer(r"^\s{2}([A-Za-z0-9_-]+):\s*\n(.*?)(?=^\s{2}[A-Za-z0-9_-]+:\s*$|\Z)", tail, re.MULTILINE | re.DOTALL):
            name = match.group(1)
            block = match.group(2)
            description_match = re.search(r"^\s{4}description:\s*(.+)", block, re.MULTILINE)
            components_match = COMPONENT_RE.search(block)
            profiles[name] = {
                "description": description_match.group(1).strip().strip('"').strip("'") if description_match else "",
                "components": inline_list(components_match.group(1)) if components_match else [],
            }
    return {"default_profile": default, "profiles": profiles, "path": path.as_posix()}


def check_profiles(payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    profiles = payload["profiles"]
    default = payload["default_profile"]
    if not profiles:
        findings.append("config/install-profiles.yaml has no profiles")
    if not default:
        findings.append("config/install-profiles.yaml missing default_profile")
    elif default not in profiles:
        findings.append(f"default_profile not found in profiles: {default}")
    for name, profile in profiles.items():
        if not profile.get("components"):
            findings.append(f"profile {name} missing components")
        if not profile.get("description"):
            findings.append(f"profile {name} missing description")
    return findings


def plan_profile(root: Path, profile: str) -> dict[str, Any]:
    payload = load_profiles(root)
    findings = check_profiles(payload)
    profiles = payload["profiles"]
    selected = profile or payload["default_profile"]
    if selected not in profiles:
        findings.append(f"unknown profile: {selected}")
        components: list[str] = []
        description = ""
    else:
        components = list(profiles[selected]["components"])
        description = str(profiles[selected]["description"])
    return {
        "ok": not findings,
        "profile": selected,
        "description": description,
        "components": components,
        "default_profile": payload["default_profile"],
        "findings": findings,
    }


def output(value: Any, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        if isinstance(value, dict):
            print(json.dumps(value, ensure_ascii=False))


def cmd_plan(root: Path, args: argparse.Namespace) -> int:
    payload = plan_profile(root, args.profile)
    output(payload, args.format)
    return 0 if payload["ok"] else 1


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    payload = load_profiles(root)
    findings = check_profiles(payload)
    result = {"ok": not findings, "findings": findings, "profiles": sorted(payload["profiles"]), "default_profile": payload["default_profile"]}
    output(result, args.format)
    return 0 if not findings else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--profile", default="")
    plan.set_defaults(func=cmd_plan)
    check = sub.add_parser("check")
    check.set_defaults(func=cmd_check)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    return args.func(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
