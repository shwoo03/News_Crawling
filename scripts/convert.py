#!/usr/bin/env python3
"""Build Codex/Claude runtime artifacts from canonical skeleton sources.

Canonical sources live in top-level `skills/`, `agents/`, `rules/`, and
`mcp/servers.yaml`. Generated targets under `.codex/` and `.claude/` are
refreshed from those sources while preserving local runtime config files.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


DEFAULT_MAPPINGS = {
    "skills": {
        "source": "skills/active",
        "targets": {"codex": ".codex/skills", "claude": ".claude/skills"},
    },
    "agents": {
        "source": "agents",
        "targets": {"codex": ".codex/agents", "claude": ".claude/agents"},
    },
    "rules": {
        "source": "rules",
        "targets": {"codex": ".codex/rules", "claude": ".claude/rules"},
    },
}

GENERATED_DIR_TARGETS = {
    ".codex/skills",
    ".codex/agents",
    ".codex/rules",
    ".claude/skills",
    ".claude/agents",
    ".claude/rules",
}
GENERATED_FILE_TARGETS = {
    ".codex/mcp.json",
    ".mcp.json",
    "CLAUDE.md",
}
GENERATED_MARKER = ".GENERATED_DO_NOT_EDIT"


@dataclass
class ConvertResult:
    copied: list[str]
    generated: list[str]
    preserved: list[str]
    warnings: list[str]
    errors: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _strip_comment(line: str) -> str:
    in_quote: str | None = None
    escaped = False
    chars: list[str] = []
    for ch in line:
        if escaped:
            chars.append(ch)
            escaped = False
            continue
        if ch == "\\":
            chars.append(ch)
            escaped = True
            continue
        if ch in {"'", '"'}:
            if in_quote == ch:
                in_quote = None
            elif in_quote is None:
                in_quote = ch
            chars.append(ch)
            continue
        if ch == "#" and in_quote is None:
            break
        chars.append(ch)
    return "".join(chars).rstrip()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    return value


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.yaml"
    if not path.exists():
        return {"mappings": DEFAULT_MAPPINGS}
    text = path.read_text(encoding="utf-8")
    mappings: dict[str, dict[str, Any]] = {}
    current: str | None = None
    in_targets = False
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":") and stripped[:-1] != "mappings":
            current = stripped[:-1]
            mappings[current] = {"targets": {}}
            in_targets = False
            continue
        if current is None:
            continue
        if indent == 4 and stripped == "targets:":
            in_targets = True
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if indent == 4 and not in_targets:
            mappings[current][key.strip()] = _parse_scalar(value)
        elif indent == 6 and in_targets:
            mappings[current].setdefault("targets", {})[key.strip()] = _parse_scalar(value)
    for name, defaults in DEFAULT_MAPPINGS.items():
        mappings.setdefault(name, defaults)
    return {"mappings": mappings}


def remove_generated_tree(path: Path, result: ConvertResult) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    result.generated.append(path.as_posix())


def copy_entries(source: Path, target: Path, result: ConvertResult) -> None:
    remove_generated_tree(target, result)
    (target / GENERATED_MARKER).write_text(
        "Generated artifact. Edit canonical sources and run python3 scripts/convert.py.\n",
        encoding="utf-8",
    )
    for item in sorted(source.iterdir()):
        if item.name == ".gitkeep":
            continue
        dst = target / item.name
        if item.is_dir():
            shutil.copytree(item, dst, symlinks=True)
        else:
            shutil.copy2(item, dst)
        result.copied.append(f"{item.as_posix()} -> {dst.as_posix()}")


def parse_mcp_servers(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    servers: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current and current.get("name"):
                servers[str(current["name"])] = {k: v for k, v in current.items() if k != "name"}
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        current[key.strip()] = _parse_scalar(value)
    if current and current.get("name"):
        servers[str(current["name"])] = {k: v for k, v in current.items() if k != "name"}
    return servers


def write_mcp(root: Path, result: ConvertResult) -> None:
    payload = {"mcpServers": parse_mcp_servers(root / "mcp" / "servers.yaml")}
    for rel in (".codex/mcp.json", ".mcp.json"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result.generated.append(rel)


def ensure_claude_entrypoint(root: Path, result: ConvertResult) -> None:
    path = root / "CLAUDE.md"
    if path.exists() or path.is_symlink():
        path.unlink()
    try:
        path.symlink_to("AGENTS.md")
        result.generated.append("CLAUDE.md -> AGENTS.md")
    except OSError:
        shutil.copy2(root / "AGENTS.md", path)
        result.warnings.append("symlink failed; copied AGENTS.md to CLAUDE.md")


def resolve_under_root(root: Path, rel: str) -> tuple[Path | None, str]:
    path = Path(rel)
    candidate = path if path.is_absolute() else root / path
    root_resolved = root.resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    try:
        normalized = resolved.relative_to(root_resolved).as_posix()
    except ValueError:
        return None, str(rel)
    return resolved, normalized


def preflight(root: Path, mappings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("skills", "agents", "rules"):
        mapping = mappings.get(key)
        if not isinstance(mapping, dict):
            errors.append(f"mapping missing: {key}")
            continue
        source_rel = str(mapping.get("source") or "").rstrip("/")
        if not source_rel:
            errors.append(f"mapping `{key}` has no source")
            continue
        source_path, source_norm = resolve_under_root(root, source_rel)
        if source_path is None:
            errors.append(f"source outside root: {source_rel}")
        elif not source_path.is_dir():
            errors.append(f"source missing: {source_norm}")
        targets = mapping.get("targets", {})
        if not isinstance(targets, dict) or not targets:
            errors.append(f"mapping `{key}` has no targets")
            continue
        for raw_target in targets.values():
            target_rel = str(raw_target or "").rstrip("/")
            target_path, target_norm = resolve_under_root(root, target_rel)
            if target_path is None:
                errors.append(f"target outside root: {target_rel}")
                continue
            if target_norm not in GENERATED_DIR_TARGETS:
                errors.append(f"target not allowlisted for directory wipe: {target_norm}")
                continue
            if target_path.exists() and not target_path.is_dir():
                errors.append(f"target is not a directory: {target_norm}")
    for rel in ("mcp/servers.yaml", "AGENTS.md"):
        path, normalized = resolve_under_root(root, rel)
        if path is None or not path.is_file():
            errors.append(f"required source missing: {normalized}")
    for rel in GENERATED_FILE_TARGETS:
        path, normalized = resolve_under_root(root, rel)
        if path is None:
            errors.append(f"generated file outside root: {normalized}")
            continue
        if path.exists() and path.is_dir():
            errors.append(f"generated file target is a directory: {normalized}")
    return errors


def _relativize(root: Path, value: str) -> str:
    path = Path(value)
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return value


def record_install_state(root: Path, result: ConvertResult, validation_status: str) -> None:
    script = root / "scripts" / "install-state.py"
    if not script.exists():
        result.warnings.append("install-state.py missing; convert event not recorded")
        return
    command = [
        sys.executable,
        str(script),
        "--root",
        str(root),
        "add",
        "--event",
        "convert_completed",
        "--validation-status",
        validation_status,
        "--selected-component",
        "canonical",
    ]
    for item in result.generated:
        command.extend(["--generated-path", _relativize(root, item)])
    for item in result.preserved:
        command.extend(["--preserved-path", item])
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
    except subprocess.SubprocessError as exc:
        result.warnings.append(f"install-state record failed: {exc}")
        return
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        result.warnings.append(f"install-state record failed: {detail}")


def verify_parity(root: Path, result: ConvertResult) -> str:
    script = root / "scripts" / "verify-parity.py"
    if not script.exists():
        result.warnings.append("verify-parity.py missing; convert validation remains unverified")
        return "unverified"
    try:
        completed = subprocess.run(
            [sys.executable, str(script), "--root", str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except subprocess.SubprocessError as exc:
        result.warnings.append(f"verify-parity failed to run: {exc}")
        return "failed"
    if completed.returncode == 0:
        return "verified"
    detail = (completed.stderr or completed.stdout).strip()
    result.warnings.append(f"verify-parity failed after convert: {detail}")
    return "failed"


def convert(root: Path) -> ConvertResult:
    result = ConvertResult(copied=[], generated=[], preserved=[], warnings=[], errors=[])
    manifest = load_manifest(root)
    mappings = manifest["mappings"]
    result.errors.extend(preflight(root, mappings))
    if result.errors:
        return result
    for key in ("skills", "agents", "rules"):
        mapping = mappings[key]
        source = root / str(mapping["source"]).rstrip("/")
        for target_rel in mapping.get("targets", {}).values():
            copy_entries(source, root / str(target_rel).rstrip("/"), result)
    write_mcp(root, result)
    for rel in (".codex/config.toml", ".claude/settings.local.json"):
        if (root / rel).exists():
            result.preserved.append(rel)
    ensure_claude_entrypoint(root, result)
    validation_status = verify_parity(root, result)
    record_install_state(root, result, validation_status)
    return result


def render_text(result: ConvertResult) -> str:
    lines = [
        "Convert",
        f"generated: {len(result.generated)}",
        f"copied: {len(result.copied)}",
        f"preserved: {len(result.preserved)}",
    ]
    for error in result.errors:
        lines.append(f"  ERROR {error}")
    for warning in result.warnings:
        lines.append(f"  WARN {warning}")
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
    result = convert(root)
    if args.format == "json":
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
