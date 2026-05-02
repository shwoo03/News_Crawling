#!/usr/bin/env python3
"""Dry-run audit of MCP server package metadata without network access."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def strip_comment(line: str) -> str:
    in_quote: str | None = None
    out: list[str] = []
    for ch in line:
        if ch in {"'", '"'}:
            in_quote = None if in_quote == ch else ch if in_quote is None else in_quote
        if ch == "#" and in_quote is None:
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return [part.strip().strip("'\"") for part in value[1:-1].split(",") if part.strip()]
    return value.strip("'\"")


def parse_servers(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / "mcp" / "servers.yaml"
    if not path.exists():
        return [], ["mcp/servers.yaml missing"]
    servers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = strip_comment(raw)
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                servers.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        current[key.strip()] = parse_scalar(value)
    if current:
        servers.append(current)
    return servers, []


def package_candidate(server: dict[str, Any]) -> str:
    args = server.get("args")
    command = str(server.get("command") or "")
    if command == "npx" and isinstance(args, list):
        for item in args:
            value = str(item)
            if value.startswith("-"):
                continue
            return value
    return ""


def audit(root: Path) -> dict[str, Any]:
    servers, findings = parse_servers(root)
    results: list[dict[str, Any]] = []
    for index, server in enumerate(servers, start=1):
        name = str(server.get("name") or f"server-{index}")
        command = str(server.get("command") or "")
        args = server.get("args")
        env_required = server.get("env_required")
        audit_passed = server.get("audit_passed")
        package = package_candidate(server)
        server_findings: list[str] = []
        if command == "npx" and isinstance(args, list) and "-y" in [str(item) for item in args]:
            server_findings.append("npx " + "-y auto-install requires supply-chain review")
        if audit_passed is not True:
            server_findings.append("audit_passed is not true")
        if not isinstance(env_required, list):
            server_findings.append("env_required must be a list")
        if command == "npx" and not package:
            server_findings.append("could not infer npm package from npx args")
        if command and command not in {"npx", "node", "python", "python3", "uvx"}:
            server_findings.append(f"unknown MCP command source: {command}")
        findings.extend(f"{name}: {finding}" for finding in server_findings)
        results.append(
            {
                "name": name,
                "transport": server.get("transport"),
                "command": command,
                "package_candidate": package,
                "audit_passed": audit_passed,
                "env_required": env_required,
                "findings": server_findings,
            }
        )
    return {"ok": not findings, "findings": findings, "servers": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("command", choices=("check",))
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    payload = audit(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["findings"]:
        print("mcp-audit findings:")
        for finding in payload["findings"]:
            print(f"  WARN {finding}")
    else:
        print(f"mcp-audit OK: {len(payload['servers'])} server(s)")
    return 1 if args.strict and payload["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
