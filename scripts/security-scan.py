#!/usr/bin/env python3
"""Scan a skeleton-based project for local security hygiene risks.

This is a read-only, standard-library scanner. It is intentionally lightweight:
it does not replace a full SAST tool, but it catches common secrets, dangerous
commands, risky hook/config patterns, and missing governance fields for copied
external code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


TEXT_EXTENSIONS = {
    "",
    ".cfg",
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
DEFAULT_MAX_FILE_SIZE = 512_000
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
SKIP_RUNTIME_DIRS = {
    ("runtime", "archive"),
    ("runtime", "external-repos"),
    ("runtime", "state"),
}
SKIP_RUNTIME_FILES = {
    ("runtime", "activity-log.jsonl"),
    ("runtime", "agent-runs.jsonl"),
    ("runtime", "review-queue.jsonl"),
}


@dataclass
class Finding:
    severity: str
    category: str
    rule: str
    path: str
    line: int
    message: str


@dataclass
class ScanResult:
    root: str
    summary: dict[str, int]
    scanned_files: int
    skipped_files: int
    findings: list[dict[str, object]]
    suppressed_findings: int = 0


ALLOWLIST_FINGERPRINT_LEN = 16


@dataclass(frozen=True)
class PatternRule:
    severity: str
    category: str
    rule: str
    pattern: re.Pattern[str]
    message: str


SECRET_RULES = [
    PatternRule("CRITICAL", "secret", "aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AWS access key-like token"),
    PatternRule("CRITICAL", "secret", "github_token", re.compile(r"\b(?:ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"), "GitHub token-like value"),
    PatternRule("CRITICAL", "secret", "openai_token", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"), "OpenAI-style token-like value"),
    PatternRule("CRITICAL", "secret", "anthropic_token", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "Anthropic-style token-like value"),
    PatternRule("CRITICAL", "secret", "slack_token", re.compile(r"\bxox[bpoas]-[A-Za-z0-9-]{10,}\b"), "Slack token-like value"),
    PatternRule("CRITICAL", "secret", "private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key block"),
]
GENERIC_SECRET_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9])(?:[A-Z0-9_]*_)?(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=:-]{20,})['\"]?"
)
DANGEROUS_COMMAND_RULES = [
    PatternRule("CRITICAL", "command", "rm_root", re.compile(r"\brm\s+-rf\s+/(?:\s|$)"), "destructive root deletion command"),
    PatternRule("CRITICAL", "command", "rm_home", re.compile(r"\brm\s+-rf\s+~(?:\s|$)"), "destructive home deletion command"),
    PatternRule("CRITICAL", "command", "fork_bomb", re.compile(r":\(\)\s*\{.*:\|:.*&.*\}"), "fork bomb pattern"),
    PatternRule("CRITICAL", "command", "mkfs_device", re.compile(r"\bmkfs\.\w+\s+/dev/"), "filesystem format command"),
    PatternRule("CRITICAL", "command", "raw_disk_write", re.compile(r"\bdd\s+if=.*of=/dev/(?:sd|nvme|hd)"), "raw disk write command"),
    PatternRule("HIGH", "command", "world_writable_root", re.compile(r"\bchmod\s+-R\s+777\s+/"), "world-writable root chmod"),
]
CONFIG_RULES = [
    PatternRule("HIGH", "config", "wildcard_shell_permission", re.compile(r"\b(?:Bash|shell|powershell|cmd)\s*\(\s*\*\s*\)"), "wildcard shell permission"),
    PatternRule("MEDIUM", "config", "npx_auto_install", re.compile(r"\bnpx\s+-y\b"), "npx auto-install can hide supply-chain changes"),
]
SCRIPT_RULES = [
    PatternRule("HIGH", "script", "python_shell_true", re.compile(r"\bshell\s*=\s*True\b"), "subprocess shell=True"),
    PatternRule("HIGH", "script", "powershell_iex", re.compile(r"\b(?:Invoke-Expression|iex)\b", re.IGNORECASE), "PowerShell Invoke-Expression"),
    PatternRule("HIGH", "script", "pipe_to_shell", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash|powershell)\b"), "download piped to shell"),
    PatternRule("MEDIUM", "script", "silent_error_suppression", re.compile(r"(?:\|\|\s*true\b|2>\s*/dev/null)"), "silent error suppression"),
]
FIELD_RE = re.compile(r"^-[ \t]+`([^`]+)`:[ \t]*([^\r\n]*?)\r?$", re.MULTILINE)
PLACEHOLDER_WORDS = {
    "example",
    "placeholder",
    "redacted",
    "your",
    "changeme",
    "dummy",
    "fake",
    "sample",
    "test",
    "token",
    "secret",
    "password",
}
COPY_LEDGER_CACHE: dict[Path, list[dict[str, object]]] = {}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def path_parts(path: Path, root: Path) -> tuple[str, ...]:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return ()


def should_skip_path(path: Path, root: Path, include_runtime: bool, max_file_size: int) -> bool:
    parts = path_parts(path, root)
    if not parts:
        return True
    if parts[:2] in SKIP_RUNTIME_FILES:
        return True
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    if not include_runtime:
        if parts[:2] in SKIP_RUNTIME_DIRS:
            return True
        if parts and parts[0] == "runtime" and parts[:2] != ("runtime", "proposals"):
            return True
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return True
    try:
        return path.stat().st_size > max_file_size
    except OSError:
        return True


def iter_scan_files(root: Path, include_runtime: bool, max_file_size: int) -> tuple[list[Path], int]:
    files: list[Path] = []
    skipped = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if should_skip_path(path, root, include_runtime, max_file_size):
            skipped += 1
            continue
        files.append(path)
    return files, skipped


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def line_is_rule_definition(path: Path, root: Path, line: str) -> bool:
    stripped = line.strip()
    in_scanner = rel(path, root) == "scripts/security-scan.py"
    return (
        in_scanner
        and (
            "re.compile(" in stripped
            or stripped.startswith("PatternRule(")
        )
    )


def value_is_placeholder(value: str) -> bool:
    lowered = value.lower()
    if any(word in lowered for word in PLACEHOLDER_WORDS):
        return True
    # Repeated characters and obvious documentation examples are low signal.
    compact = re.sub(r"[^A-Za-z0-9]", "", value)
    return len(set(compact)) <= 4 if compact else True


def clean_field_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def parse_markdown_fields(text: str) -> dict[str, str]:
    return {match.group(1): clean_field_value(match.group(2)) for match in FIELD_RE.finditer(text)}


def read_copy_ledger(root: Path) -> list[dict[str, object]]:
    resolved_root = root.resolve()
    cached = COPY_LEDGER_CACHE.get(resolved_root)
    if cached is not None:
        return cached
    path = root / "runtime" / "reference-copy-ledger.jsonl"
    records: list[dict[str, object]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    COPY_LEDGER_CACHE[resolved_root] = records
    return records


def ledger_has_match(root: Path, artifact_path: Path, text: str) -> bool:
    artifact_rel = rel(artifact_path, root)
    for record in read_copy_ledger(root):
        candidate_card = str(record.get("candidate_card", "")).strip()
        proposal = str(record.get("proposal", "")).strip()
        local_path = str(record.get("local_path", "")).strip()
        if artifact_rel in {candidate_card, proposal}:
            return True
        if local_path and local_path in text:
            return True
    return False


def add_pattern_findings(
    findings: list[Finding],
    root: Path,
    path: Path,
    line_no: int,
    line: str,
    rules: Iterable[PatternRule],
) -> None:
    if line_is_rule_definition(path, root, line):
        return
    for rule in rules:
        if rule.pattern.search(line):
            findings.append(
                Finding(
                    rule.severity,
                    rule.category,
                    rule.rule,
                    rel(path, root),
                    line_no,
                    rule.message,
                )
            )


def scan_generic_secret(findings: list[Finding], root: Path, path: Path, line_no: int, line: str) -> None:
    if line_is_rule_definition(path, root, line):
        return
    match = GENERIC_SECRET_RE.search(line)
    if not match:
        return
    value = match.group(1)
    if value_is_placeholder(value):
        return
    findings.append(
        Finding(
            "HIGH",
            "secret",
            "generic_secret_assignment",
            rel(path, root),
            line_no,
            "generic secret-like assignment",
        )
    )


def scan_reference_copy_governance(findings: list[Finding], root: Path, path: Path, lines: list[str]) -> None:
    parts = path_parts(path, root)
    if not (
        parts[:2] == ("research", "reference-candidates")
        or parts[:3] == ("runtime", "proposals", "reference-adoption")
    ):
        return
    text = "\n".join(lines)
    fields = parse_markdown_fields(text)
    has_copy_candidate = fields.get("adoption_decision") == "copy"
    has_partial_copy_proposal = fields.get("absorption_mode") == "partial_copy"
    if not has_copy_candidate and not has_partial_copy_proposal:
        return
    required_terms = ("license", "revision", "copy_boundary")
    missing = [term for term in required_terms if term not in text]
    if missing:
        findings.append(
            Finding(
                "MEDIUM",
                "governance",
                "copy_governance_missing_terms",
                rel(path, root),
                1,
                "copy/partial_copy artifact is missing: " + ", ".join(missing),
            )
        )
    if not ledger_has_match(root, path, text):
        findings.append(
            Finding(
                "MEDIUM",
                "governance",
                "copy_ledger_missing_entry",
                rel(path, root),
                1,
                "copy/partial_copy artifact has no matching runtime/reference-copy-ledger.jsonl entry",
            )
        )


def scan_file(root: Path, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = read_lines(path)
    for index, line in enumerate(lines, start=1):
        add_pattern_findings(findings, root, path, index, line, SECRET_RULES)
        scan_generic_secret(findings, root, path, index, line)
        add_pattern_findings(findings, root, path, index, line, DANGEROUS_COMMAND_RULES)
        add_pattern_findings(findings, root, path, index, line, CONFIG_RULES)
        add_pattern_findings(findings, root, path, index, line, SCRIPT_RULES)
    scan_reference_copy_governance(findings, root, path, lines)
    return findings


def read_allowlist(root: Path) -> list[dict[str, object]]:
    path = root / "rules" / "security-scan-allowlist.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def finding_fingerprint(root: Path, finding: Finding) -> str:
    path = root / finding.path
    line_text = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if 1 <= finding.line <= len(lines):
            line_text = lines[finding.line - 1].strip()
    except OSError:
        line_text = ""
    value = f"{finding.rule}\n{finding.path}\n{line_text}\n{finding.message}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:ALLOWLIST_FINGERPRINT_LEN]


def allowlist_entry_matches(root: Path, item: dict[str, object], finding: Finding) -> bool:
    if str(item.get("rule", "")).strip() != finding.rule:
        return False
    if str(item.get("path", "")).strip() != finding.path:
        return False
    line = item.get("line")
    fingerprint = str(item.get("fingerprint", "")).strip()
    if line is None and not fingerprint:
        return False
    if line is not None:
        try:
            if int(line) != finding.line:
                return False
        except (TypeError, ValueError):
            return False
    if fingerprint and fingerprint != finding_fingerprint(root, finding):
        return False
    return bool(str(item.get("reason", "")).strip())


def validate_allowlist(root: Path, findings: list[Finding], allowlist: list[dict[str, object]]) -> list[Finding]:
    validation_findings: list[Finding] = []
    for index, item in enumerate(allowlist, start=1):
        rule = str(item.get("rule", "")).strip()
        path = str(item.get("path", "")).strip()
        reason = str(item.get("reason", "")).strip()
        line = item.get("line")
        fingerprint = str(item.get("fingerprint", "")).strip()
        if not rule or not path:
            validation_findings.append(
                Finding("HIGH", "allowlist", "allowlist_invalid", "rules/security-scan-allowlist.json", index, "allowlist entry requires rule and path")
            )
            continue
        if not reason:
            validation_findings.append(
                Finding("HIGH", "allowlist", "allowlist_invalid", "rules/security-scan-allowlist.json", index, "allowlist entry requires reason")
            )
        if line is None and not fingerprint:
            validation_findings.append(
                Finding(
                    "HIGH",
                    "allowlist",
                    "allowlist_invalid",
                    "rules/security-scan-allowlist.json",
                    index,
                    "allowlist entry requires line or fingerprint",
                )
            )
            continue
        if line is not None:
            try:
                int(line)
            except (TypeError, ValueError):
                validation_findings.append(
                    Finding("HIGH", "allowlist", "allowlist_invalid", "rules/security-scan-allowlist.json", index, "allowlist line must be an integer")
                )
                continue
        if not any(allowlist_entry_matches(root, item, finding) for finding in findings):
            validation_findings.append(
                Finding(
                    "HIGH",
                    "allowlist",
                    "allowlist_stale",
                    "rules/security-scan-allowlist.json",
                    index,
                    f"allowlist entry no longer matches an active finding: {rule} {path}",
                )
            )
    return validation_findings


def finding_is_allowed(root: Path, finding: Finding, allowlist: list[dict[str, object]]) -> bool:
    for item in allowlist:
        if allowlist_entry_matches(root, item, finding):
            return True
    return False


def run_scan(root: Path, include_runtime: bool, max_file_size: int) -> ScanResult:
    files, skipped = iter_scan_files(root, include_runtime, max_file_size)
    findings: list[Finding] = []
    for path in files:
        findings.extend(scan_file(root, path))
    allowlist = read_allowlist(root)
    active_findings = [finding for finding in findings if not finding_is_allowed(root, finding, allowlist)]
    suppressed = len(findings) - len(active_findings)
    active_findings.extend(validate_allowlist(root, findings, allowlist))
    counter = Counter(finding.severity for finding in active_findings)
    summary = {severity: counter.get(severity, 0) for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")}
    return ScanResult(
        root=str(root),
        summary=summary,
        scanned_files=len(files),
        skipped_files=skipped,
        findings=[asdict(finding) for finding in active_findings],
        suppressed_findings=suppressed,
    )


def render_text(result: ScanResult) -> str:
    total = sum(result.summary.values())
    lines = [
        "Security Scan",
        f"root: {result.root}",
        "summary: "
        + ", ".join(f"{name.lower()}={count}" for name, count in result.summary.items())
        + f", total={total}",
        f"scanned_files: {result.scanned_files}",
        f"skipped_files: {result.skipped_files}",
        f"suppressed_findings: {result.suppressed_findings}",
    ]
    if not result.findings:
        lines.append("findings: none")
        return "\n".join(lines)
    lines.append("findings:")
    for finding in result.findings:
        lines.append(
            f"  {finding['severity']:<8} {finding['path']}:{finding['line']} "
            f"{finding['rule']} - {finding['message']}"
        )
    return "\n".join(lines)


def has_strict_failure(result: ScanResult) -> bool:
    return result.summary.get("CRITICAL", 0) > 0 or result.summary.get("HIGH", 0) > 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when HIGH or CRITICAL findings exist.")
    parser.add_argument("--include-runtime", action="store_true", help="Scan runtime files normally excluded by default.")
    parser.add_argument("--max-file-size", type=int, default=DEFAULT_MAX_FILE_SIZE, help="Maximum file size in bytes.")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    result = run_scan(root, args.include_runtime, args.max_file_size)
    if args.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 1 if args.strict and has_strict_failure(result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
