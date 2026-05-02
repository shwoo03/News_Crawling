#!/usr/bin/env python3
"""Validate local plugin manifests and marketplace metadata."""

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


PLUGIN_PATHS = [".codex-plugin/plugin.json", ".claude-plugin/plugin.json"]
REQUIRED_PLUGIN_FIELDS = {"name", "version", "description", "entrypoint"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_json(path: Path, root: Path, findings: list[str]) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        findings.append(f"{path.relative_to(root).as_posix()} unreadable: {exc}")
        return None
    except json.JSONDecodeError as exc:
        findings.append(f"{path.relative_to(root).as_posix()} invalid JSON: {exc}")
        return None
    return value


def is_safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def check_plugin(root: Path, rel: str, findings: list[str]) -> dict[str, Any] | None:
    path = root / rel
    if not path.is_file():
        findings.append(f"{rel} missing")
        return None
    payload = read_json(path, root, findings)
    if not isinstance(payload, dict):
        findings.append(f"{rel} must contain a JSON object")
        return None
    missing = sorted(REQUIRED_PLUGIN_FIELDS.difference(payload))
    if missing:
        findings.append(f"{rel} missing field(s): {', '.join(missing)}")
    for field in REQUIRED_PLUGIN_FIELDS:
        if field in payload and not str(payload.get(field) or "").strip():
            findings.append(f"{rel} field `{field}` is blank")
    if payload.get("version") and not VERSION_RE.match(str(payload["version"])):
        findings.append(f"{rel} version must be semver-like")
    entrypoint = str(payload.get("entrypoint") or "")
    if entrypoint and (not is_safe_relative(entrypoint) or not (root / entrypoint).exists()):
        findings.append(f"{rel} entrypoint invalid or missing: {entrypoint}")
    return payload


def check_marketplace(root: Path, plugins: list[dict[str, Any]], findings: list[str]) -> list[dict[str, Any]]:
    path = root / ".agents" / "plugins" / "marketplace.json"
    if not path.exists():
        findings.append(".agents/plugins/marketplace.json missing")
        return []
    payload = read_json(path, root, findings)
    if not isinstance(payload, dict) or not isinstance(payload.get("plugins"), list):
        findings.append(".agents/plugins/marketplace.json must contain plugins list")
        return []
    entries = [item for item in payload["plugins"] if isinstance(item, dict)]
    plugin_names = {str(plugin.get("name") or "") for plugin in plugins}
    plugin_versions = {str(plugin.get("version") or "") for plugin in plugins}
    for index, entry in enumerate(entries, start=1):
        for field in ("id", "name", "version", "path"):
            if not str(entry.get(field) or "").strip():
                findings.append(f"marketplace plugin {index} missing `{field}`")
        entry_path = str(entry.get("path") or "")
        if entry_path and not is_safe_relative(entry_path):
            findings.append(f"marketplace plugin {index} path must be relative and stay in repo")
        if plugin_names and str(entry.get("id") or "") not in plugin_names:
            findings.append(f"marketplace plugin {index} id does not match plugin manifest name")
        if plugin_versions and str(entry.get("version") or "") not in plugin_versions:
            findings.append(f"marketplace plugin {index} version does not match plugin manifest version")
    return entries


def run_check(root: Path) -> dict[str, Any]:
    findings: list[str] = []
    plugins: list[dict[str, Any]] = []
    for rel in PLUGIN_PATHS:
        plugin = check_plugin(root, rel, findings)
        if plugin:
            plugins.append(plugin)
    marketplace = check_marketplace(root, plugins, findings)
    return {"ok": not findings, "findings": findings, "plugins": plugins, "marketplace_entries": marketplace}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("command", choices=("check",))
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    payload = run_check(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["findings"]:
        print("plugin manifest findings:")
        for finding in payload["findings"]:
            print(f"  ERROR {finding}")
    else:
        print(f"plugin manifests OK: {len(payload['plugins'])} plugin(s)")
    return 1 if payload["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
