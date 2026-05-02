#!/usr/bin/env python3
"""Validate schema documents and schema-backed runtime/config contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_catalog import validate_catalog


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


TYPE_MAP = {
    "string": str,
    "object": dict,
    "array": list,
    "boolean": bool,
    "null": type(None),
}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path, root: Path, findings: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        findings.append(f"{rel(root, path)} unreadable: {exc}")
    except json.JSONDecodeError as exc:
        findings.append(f"{rel(root, path)} invalid JSON: {exc}")
    return None


def type_names(spec: Any) -> list[str]:
    value = spec.get("type") if isinstance(spec, dict) else spec
    return list(value) if isinstance(value, list) else [str(value)]


def matches_type(value: Any, names: list[str]) -> bool:
    for name in names:
        expected = TYPE_MAP.get(name)
        if expected is None:
            continue
        if name == "boolean":
            if isinstance(value, bool):
                return True
        elif name != "boolean" and isinstance(value, expected) and not isinstance(value, bool):
            return True
    return False


def validate_object(schema: dict[str, Any], value: Any, label: str) -> list[str]:
    findings: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    for field in schema.get("required", []):
        if field not in value:
            findings.append(f"{label} missing field `{field}`")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return findings
    for field, spec in properties.items():
        if field not in value or not isinstance(spec, dict):
            continue
        names = type_names(spec)
        if not matches_type(value[field], names):
            findings.append(f"{label}.{field} must be type {'/'.join(names)}")
            continue
        if "enum" in spec and value[field] not in spec["enum"]:
            findings.append(f"{label}.{field} must be one of {', '.join(map(str, spec['enum']))}")
        if spec.get("pattern") == "semver" and isinstance(value[field], str) and not SEMVER_RE.match(value[field]):
            findings.append(f"{label}.{field} must be semver-like")
        if spec.get("path") == "relative" and isinstance(value[field], str):
            path = Path(value[field])
            if path.is_absolute() or ".." in path.parts or not value[field].strip():
                findings.append(f"{label}.{field} must be a safe relative path")
        if names == ["array"] and isinstance(value[field], list) and isinstance(spec.get("items"), dict):
            item_names = type_names(spec["items"])
            for index, item in enumerate(value[field], start=1):
                if not matches_type(item, item_names):
                    findings.append(f"{label}.{field}[{index}] must be type {'/'.join(item_names)}")
    return findings


def read_jsonl(path: Path, root: Path, findings: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"{rel(root, path)}:{line_no} invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            findings.append(f"{rel(root, path)}:{line_no} record must be an object")
            continue
        records.append(value)
    return records


def load_schemas(root: Path, findings: list[str]) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    schema_dir = root / "schemas"
    if not schema_dir.is_dir():
        findings.append("schemas/ directory missing")
        return schemas
    for path in sorted(schema_dir.glob("*.schema.json")):
        payload = read_json(path, root, findings)
        if not isinstance(payload, dict):
            findings.append(f"{rel(root, path)} must contain an object")
            continue
        for field in ("schema_version", "name", "type"):
            if not str(payload.get(field) or "").strip():
                findings.append(f"{rel(root, path)} missing `{field}`")
        name = str(payload.get("name") or path.stem.replace(".schema", ""))
        schemas[name] = payload
    return schemas


def check_catalog(root: Path, schema: dict[str, Any] | None) -> list[str]:
    modes = tuple((schema or {}).get("required_routing_modes", ["decide", "research", "closeout", "maintain", "build"]))
    return validate_catalog(root, required_modes=modes)


def run_check(root: Path) -> dict[str, Any]:
    findings: list[str] = []
    schemas = load_schemas(root, findings)
    checked: dict[str, int] = {"schemas": len(schemas)}

    install_schema = schemas.get("install-state")
    if install_schema:
        records = read_jsonl(root / "runtime" / "install-state.jsonl", root, findings)
        checked["install_state_records"] = len(records)
        for index, record in enumerate(records, start=1):
            findings.extend(validate_object(install_schema, record, f"runtime/install-state.jsonl record {index}"))

    plugin_schema = schemas.get("plugin-manifest")
    if plugin_schema:
        for rel_path in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
            payload = read_json(root / rel_path, root, findings)
            if payload is not None:
                checked[rel_path] = 1
                findings.extend(validate_object(plugin_schema, payload, rel_path))

    snapshot_schema = schemas.get("session-snapshot")
    if snapshot_schema and (root / "runtime" / "session-snapshot.json").exists():
        payload = read_json(root / "runtime" / "session-snapshot.json", root, findings)
        if payload is not None:
            checked["session_snapshot"] = 1
            findings.extend(validate_object(snapshot_schema, payload, "runtime/session-snapshot.json"))

    findings.extend(check_catalog(root, schemas.get("script-catalog")))
    return {"ok": not findings, "findings": findings, "checked": checked, "schemas": sorted(schemas)}


def render_text(payload: dict[str, Any]) -> str:
    lines = ["Schema Check", f"schemas: {', '.join(payload['schemas']) if payload['schemas'] else 'none'}"]
    if payload["findings"]:
        lines.append("findings:")
        lines.extend(f"  ERROR {finding}" for finding in payload["findings"])
    else:
        lines.append("  OK schema-backed contracts passed")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Reserved for compatibility; schema errors always fail.")
    parser.add_argument("command", nargs="?", default="check", choices=("check",))
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    payload = run_check(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 1 if payload["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
