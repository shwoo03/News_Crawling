#!/usr/bin/env python3
"""Verify generated Codex and Claude artifacts match canonical sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import convert as convert_lib


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


@dataclass
class Finding:
    severity: str
    check: str
    detail: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def entry_names(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    ignored = {".gitkeep", convert_lib.GENERATED_MARKER}
    return sorted(item.name for item in path.iterdir() if item.name not in ignored)


def compare_names(label: str, expected: list[str], actual: list[str], findings: list[Finding]) -> None:
    if expected == actual:
        return
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    detail = f"{label} mismatch"
    if missing:
        detail += f"; missing={missing}"
    if extra:
        detail += f"; extra={extra}"
    findings.append(Finding("ERROR", f"{label}_parity", detail))


def recursive_files(path: Path) -> dict[str, str]:
    if not path.is_dir():
        return {}
    files: dict[str, str] = {}
    for item in sorted(path.rglob("*")):
        if item.name in {".gitkeep", convert_lib.GENERATED_MARKER} or not item.is_file():
            continue
        rel = item.relative_to(path).as_posix()
        if item.is_symlink():
            digest = "symlink:" + item.readlink().as_posix()
        else:
            digest = hashlib.sha256(item.read_bytes()).hexdigest()
        files[rel] = digest
    return files


def compare_tree(label: str, source: Path, target: Path, findings: list[Finding]) -> None:
    if not source.is_dir():
        findings.append(Finding("ERROR", f"{label}_source", f"source missing: {source.as_posix()}"))
        return
    if not target.is_dir():
        findings.append(Finding("ERROR", f"{label}_target", f"target missing: {target.as_posix()}"))
        return
    compare_names(label, entry_names(source), entry_names(target), findings)
    expected = recursive_files(source)
    actual = recursive_files(target)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(rel for rel in set(expected) & set(actual) if expected[rel] != actual[rel])
    if missing or extra or changed:
        detail = f"{label} content mismatch"
        if missing:
            detail += f"; missing_files={missing}"
        if extra:
            detail += f"; extra_files={extra}"
        if changed:
            detail += f"; changed_files={changed}"
        findings.append(Finding("ERROR", f"{label}_content", detail))


def load_mcp_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    servers = payload.get("mcpServers", {})
    if isinstance(servers, dict):
        return sorted(servers)
    if isinstance(servers, list):
        return sorted(str(item.get("name")) for item in servers if isinstance(item, dict) and item.get("name"))
    return []


def load_json(path: Path) -> object:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_mcp_payload(label: str, expected: dict[str, object], path: Path, findings: list[Finding]) -> None:
    if not path.exists():
        findings.append(Finding("ERROR", f"{label}_mcp", f"{path.as_posix()} missing"))
        return
    try:
        actual = load_json(path)
    except json.JSONDecodeError as exc:
        findings.append(Finding("ERROR", f"{label}_mcp", f"{path.as_posix()} invalid JSON: {exc}"))
        return
    if actual != expected:
        findings.append(Finding("ERROR", f"{label}_mcp", f"{path.as_posix()} differs from canonical mcp/servers.yaml conversion"))


def compare_claude_entrypoint(root: Path, findings: list[Finding]) -> None:
    path = root / "CLAUDE.md"
    agents = root / "AGENTS.md"
    if not path.exists():
        findings.append(Finding("ERROR", "claude_entrypoint", "CLAUDE.md missing"))
        return
    if path.is_symlink():
        try:
            if path.resolve(strict=False) == agents.resolve(strict=False):
                return
        except OSError:
            pass
        findings.append(Finding("ERROR", "claude_entrypoint", "CLAUDE.md symlink does not resolve to AGENTS.md"))
        return
    if path.read_text(encoding="utf-8") != agents.read_text(encoding="utf-8"):
        findings.append(Finding("ERROR", "claude_entrypoint", "CLAUDE.md file fallback differs from AGENTS.md"))


def run_check(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    manifest = convert_lib.load_manifest(root)
    mappings = manifest.get("mappings", {})
    for key in ("skills", "agents", "rules"):
        mapping = mappings.get(key, {})
        source = root / str(mapping.get("source", "")).rstrip("/")
        for target_name, target_rel in sorted(mapping.get("targets", {}).items()):
            compare_tree(f"{target_name}_{key}", source, root / str(target_rel).rstrip("/"), findings)

    expected_mcp_payload = {"mcpServers": convert_lib.parse_mcp_servers(root / "mcp" / "servers.yaml")}
    compare_mcp_payload("codex", expected_mcp_payload, root / ".codex" / "mcp.json", findings)
    compare_mcp_payload("claude", expected_mcp_payload, root / ".mcp.json", findings)
    compare_claude_entrypoint(root, findings)
    return findings


def render_text(findings: list[Finding]) -> str:
    if not findings:
        return "parity OK: canonical sources match generated artifacts"
    lines = ["parity findings:"]
    for finding in findings:
        lines.append(f"  {finding.severity:<5} [{finding.check}] {finding.detail}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    findings = run_check(root)
    if args.format == "json":
        print(json.dumps({"root": str(root), "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings))
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
