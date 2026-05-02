#!/usr/bin/env python3
"""Report when operational changes lack matching docs/tests/catalog rationale."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SENSITIVE_PREFIXES = ("scripts/", "hooks/", "rules/", "skills/")
SUPPORT_PREFIXES = ("tests/", "docs/", "schemas/")
SUPPORT_PATHS = {"scripts/catalog.yaml", "manifest.yaml", "config/policy.yaml", "config/agent-team.yaml"}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def git_changed_paths(root: Path) -> tuple[list[str], str]:
    result = subprocess.run(["git", "status", "--short"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return [], result.stderr.strip() or result.stdout.strip()
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        paths.append(path)
    return paths, ""


def analyze(root: Path) -> dict[str, Any]:
    paths, error = git_changed_paths(root)
    findings: list[dict[str, str]] = []
    if error:
        return {"ok": False, "findings": [{"level": "warn", "check": "git_status_unavailable", "detail": error}], "changed_paths": []}
    operational = [path for path in paths if path.startswith(SENSITIVE_PREFIXES)]
    supporting = [path for path in paths if path.startswith(SUPPORT_PREFIXES) or path in SUPPORT_PATHS or path.startswith("runtime/proposals/")]
    if operational and not supporting:
        findings.append(
            {
                "level": "warn",
                "check": "change_set_drift",
                "detail": "operational files changed without docs/tests/schema/catalog/rationale changes: " + ", ".join(operational[:8]),
            }
        )
    return {"ok": not findings, "findings": findings, "changed_paths": paths, "operational_paths": operational, "supporting_paths": supporting}


def render_text(payload: dict[str, Any]) -> str:
    lines = ["Change Drift Check"]
    if payload.get("findings"):
        lines.extend(f"  {item['level'].upper()} {item['check']}: {item['detail']}" for item in payload["findings"])
    else:
        lines.append("  OK no unsupported operational drift detected")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    payload = analyze(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 1 if args.strict and payload.get("findings") else 0


if __name__ == "__main__":
    raise SystemExit(main())
