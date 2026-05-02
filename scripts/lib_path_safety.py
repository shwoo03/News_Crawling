"""Shared path safety checks for harness-level write/delete decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


WRITE_OPERATIONS = {"write", "delete"}
GENERATED_ROOTS = {".codex", ".claude"}
PROTECTED_BASENAMES = {".env", ".env.local", ".env.production", ".env.development"}
PROTECTED_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
PROTECTED_PARTS = {".ssh", ".aws"}
PRIVATE_KEY_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa"}


@dataclass
class PathSafetyResult:
    decision: str
    reason: str
    root: str
    path: str
    resolved_path: str
    operation: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _resolve_target(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve(strict=False)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _repo_parts(path: Path, root: Path) -> tuple[str, ...]:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return ()


def evaluate_path(root: Path, value: str, operation: str) -> PathSafetyResult:
    root = root.resolve(strict=False)
    operation = (operation or "").strip().lower()
    if operation not in WRITE_OPERATIONS:
        return PathSafetyResult("deny", "unsupported operation", root.as_posix(), value, value, operation)
    if not value or not str(value).strip():
        return PathSafetyResult("deny", "missing path", root.as_posix(), value, value, operation)

    resolved = _resolve_target(root, value)
    if not _is_under(resolved, root):
        return PathSafetyResult(
            "deny",
            "resolved path is outside repository root",
            root.as_posix(),
            value,
            resolved.as_posix(),
            operation,
        )

    parts = _repo_parts(resolved, root)
    if not parts:
        return PathSafetyResult("deny", "repository root is not a safe target", root.as_posix(), value, resolved.as_posix(), operation)

    if parts[0] in GENERATED_ROOTS:
        return PathSafetyResult(
            "deny",
            "generated artifact paths must be produced through convert/parity flow",
            root.as_posix(),
            value,
            resolved.as_posix(),
            operation,
        )

    basename = resolved.name
    lower_basename = basename.lower()
    lower_parts = {part.lower() for part in parts}
    if lower_basename in PROTECTED_BASENAMES or lower_basename.startswith(".env."):
        return PathSafetyResult("deny", "secret environment file target", root.as_posix(), value, resolved.as_posix(), operation)
    if lower_basename in PRIVATE_KEY_NAMES or any(lower_basename.endswith(suffix) for suffix in PROTECTED_SUFFIXES):
        return PathSafetyResult("deny", "private key or certificate target", root.as_posix(), value, resolved.as_posix(), operation)
    if PROTECTED_PARTS.intersection(lower_parts):
        return PathSafetyResult("deny", "protected credential directory target", root.as_posix(), value, resolved.as_posix(), operation)

    return PathSafetyResult("ask", "path is inside repository and not protected", root.as_posix(), value, resolved.as_posix(), operation)
