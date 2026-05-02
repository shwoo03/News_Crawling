#!/usr/bin/env python3
"""Validate reference-adoption dry-run proposal documents.

The checker validates concrete proposal files under
runtime/proposals/reference-adoption/. README.md and _template.md are skipped.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


ADOPTION_REQUIRED_FIELDS = [
    "status",
    "created_at",
    "candidate_card",
    "proposal_type",
    "approval_required",
    "absorption_mode",
    "recommended_mode",
    "reuse_boundary",
    "direct_implementation_reason",
    "decision_source",
    "decision",
    "decided_at",
    "decided_by",
    "applied_in",
    "validation_result",
]
REFRESH_REQUIRED_FIELDS = [
    "status",
    "created_at",
    "candidate_card",
    "proposal_type",
    "approval_required",
    "decision_source",
    "decision",
    "decided_at",
    "decided_by",
    "applied_in",
    "validation_result",
]
COMMON_ALLOWED_VALUES = {
    "status": {"proposed", "accepted", "rejected", "applied", "deferred"},
    "proposal_type": {"reference_adoption_dry_run", "reference_refresh"},
    "approval_required": {"yes", "no"},
    "decision": {"pending", "accepted", "rejected", "applied", "deferred"},
}
ADOPTION_ALLOWED_VALUES = {
    "absorption_mode": {
        "dependency",
        "wrapper",
        "partial_copy",
        "concept_only",
        "direct_implementation",
        "mixed",
    },
}
ADOPTION_REQUIRED_HEADINGS = [
    "## 상태",
    "## 한 문장 정의",
    "## 근거",
    "## 적용하지 않을 것",
    "## 모듈형 흡수 판단",
    "## 제안 변경",
    "## 기대 효과",
    "## 위험",
    "## 검증 계획",
    "## 롤백 또는 중단 조건",
    "## 승인 후 실제 변경 범위",
    "## 최종 결정 기록",
]
REFRESH_REQUIRED_HEADINGS = [
    "## 상태",
    "## 한 문장 정의",
    "## 근거",
    "## 제안 변경",
    "## 검증 계획",
    "## 최종 결정 기록",
]
ADOPTION_REQUIRED_PHRASES = [
    "python scripts/verify-skeleton.py",
    "python scripts/validate-reference-candidates.py",
    "python scripts/validate-reference-proposals.py",
]
REFRESH_REQUIRED_PHRASES = [
    "python scripts/verify-skeleton.py",
    "python scripts/validate-reference-proposals.py",
]
SKIP_FILES = {"README.md", "_template.md"}
FIELD_RE = re.compile(r"^-[ \t]+`([^`]+)`:[ \t]*([^\r\n]*?)\r?$", re.MULTILINE)


@dataclass
class Finding:
    path: Path
    message: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def proposal_dir(root: Path) -> Path:
    return root / "runtime" / "proposals" / "reference-adoption"


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    matches = list(FIELD_RE.finditer(text))
    for match in matches:
        fields[match.group(1)] = match.group(2).strip()
    return fields


def is_blank(value: str) -> bool:
    return value.strip() in {"", "-", "TBD", "todo", "TODO"}


def clean_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def proposal_files(root: Path) -> list[Path]:
    directory = proposal_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.md")
        if path.name not in SKIP_FILES and not path.name.startswith(".")
    )


def validate_headings(path: Path, text: str, headings: list[str], findings: list[Finding]) -> None:
    for heading in headings:
        if heading not in text:
            findings.append(Finding(path, f"missing heading `{heading}`"))


def validate_fields(root: Path, path: Path, fields: dict[str, str], proposal_type: str, findings: list[Finding]) -> None:
    decision = clean_value(fields.get("decision", ""))
    absorption_mode = clean_value(fields.get("absorption_mode", ""))
    required_fields = REFRESH_REQUIRED_FIELDS if proposal_type == "reference_refresh" else ADOPTION_REQUIRED_FIELDS
    for field in required_fields:
        if field not in fields:
            findings.append(Finding(path, f"missing field `{field}`"))
            continue
        if field in {"decision_source", "decided_at", "decided_by", "applied_in", "validation_result"}:
            # Pending proposals legitimately leave final-decision fields blank.
            if decision == "pending":
                continue
        if is_blank(fields[field]):
            findings.append(Finding(path, f"field `{field}` is blank"))
    allowed_values = dict(COMMON_ALLOWED_VALUES)
    if proposal_type == "reference_adoption_dry_run":
        allowed_values.update(ADOPTION_ALLOWED_VALUES)
    for field, allowed in allowed_values.items():
        value = clean_value(fields.get(field, ""))
        if value and value not in allowed:
            findings.append(
                Finding(
                    path,
                    f"field `{field}` has invalid value `{value}`; expected one of {sorted(allowed)}",
                )
            )
    candidate = clean_value(fields.get("candidate_card", ""))
    if candidate and not is_blank(candidate) and not (root / candidate).exists():
        findings.append(Finding(path, f"candidate_card target does not exist: `{candidate}`"))
    if proposal_type == "reference_adoption_dry_run" and absorption_mode == "partial_copy":
        copy_boundary = clean_value(fields.get("copy_boundary", ""))
        if is_blank(copy_boundary):
            findings.append(
                Finding(
                    path,
                    "partial_copy proposal requires non-blank field `copy_boundary`",
                )
            )
    if proposal_type == "reference_adoption_dry_run" and absorption_mode == "direct_implementation":
        reason = clean_value(fields.get("direct_implementation_reason", ""))
        if is_blank(reason) or reason.lower() in {"not applicable", "n/a"}:
            findings.append(
                Finding(
                    path,
                    "direct_implementation proposal requires a concrete `direct_implementation_reason`",
                )
            )


def validate_list_section(path: Path, text: str, heading: str, findings: list[Finding]) -> None:
    index = text.find(heading)
    if index == -1:
        return
    tail = text[index + len(heading) :]
    next_heading = tail.find("\n## ")
    block = tail if next_heading == -1 else tail[:next_heading]
    if not re.search(r"^\s*-\s+\S", block, re.MULTILINE):
        findings.append(Finding(path, f"section `{heading}` has no bullet items"))


def validate_content(path: Path, text: str, proposal_type: str, findings: list[Finding]) -> None:
    if proposal_type == "reference_refresh":
        for phrase in REFRESH_REQUIRED_PHRASES:
            if phrase not in text:
                findings.append(Finding(path, f"missing validation command `{phrase}`"))
        return
    for heading in (
        "## 적용하지 않을 것",
        "## 모듈형 흡수 판단",
        "## 기대 효과",
        "## 위험",
        "## 롤백 또는 중단 조건",
        "## 승인 후 실제 변경 범위",
    ):
        validate_list_section(path, text, heading, findings)
    for phrase in ADOPTION_REQUIRED_PHRASES:
        if phrase not in text:
            findings.append(Finding(path, f"missing validation command `{phrase}`"))
    marker = "Source-backed evidence:"
    if marker not in text:
        findings.append(Finding(path, "missing source-backed evidence section"))
    else:
        tail = text[text.find(marker) + len(marker) :]
        next_heading = tail.find("\n## ")
        block = tail if next_heading == -1 else tail[:next_heading]
        if not re.search(r"^\s*-\s+\S", block, re.MULTILINE):
            findings.append(Finding(path, "source-backed evidence section has no bullet items"))


def validate(root: Path) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files = proposal_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8")
        fields = parse_fields(text)
        proposal_type = clean_value(fields.get("proposal_type", ""))
        if proposal_type not in COMMON_ALLOWED_VALUES["proposal_type"]:
            findings.append(Finding(path, f"field `proposal_type` has invalid value `{proposal_type}`; expected one of {sorted(COMMON_ALLOWED_VALUES['proposal_type'])}"))
            proposal_type = "reference_adoption_dry_run"
        headings = REFRESH_REQUIRED_HEADINGS if proposal_type == "reference_refresh" else ADOPTION_REQUIRED_HEADINGS
        validate_headings(path, text, headings, findings)
        validate_fields(root, path, fields, proposal_type, findings)
        validate_content(path, text, proposal_type, findings)
    return findings, len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=None,
        help="Project root (defaults to this script's repository root).",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root()
    findings, count = validate(root)
    if findings:
        print("reference proposal findings:")
        for finding in findings:
            rel = finding.path.relative_to(root).as_posix()
            print(f"  ERROR {rel}: {finding.message}")
        print(f"checked {count} reference proposal(s), {len(findings)} error(s)")
        return 1
    print(f"reference proposals OK: {count} proposal(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
