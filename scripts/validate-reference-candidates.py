#!/usr/bin/env python3
"""Validate external reference candidate cards.

The checker intentionally validates only concrete candidate files under
research/reference-candidates/. README.md and _template.md are skipped.
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


REQUIRED_FIELDS = [
    "name",
    "url",
    "source_type",
    "status",
    "searched_for",
    "created_at",
    "reviewed_at",
    "reviewer",
    "problem_statement",
    "why_it_matters",
    "expected_value",
    "evidence_summary",
    "local_clone_path",
    "checked_revision",
    "freshness_signal",
    "maintenance_signal",
    "documentation_signal",
    "validation_signal",
    "sources",
    "license",
    "security_or_privacy_risk",
    "maintenance_risk",
    "complexity_risk",
    "dependency_risk",
    "fit_risk",
    "applies_to",
    "adoption_decision",
    "decision_reason",
    "next_action",
    "proposal_needed",
    "behavior_change",
    "validation_plan",
    "rollback_or_stop_condition",
    "approval_required",
    "final_status",
    "validation_result",
    "activity_log_entry",
    "notes",
]
ALLOWED_VALUES = {
    "source_type": {"repository", "official_docs", "article", "paper", "existing_reference"},
    "status": {"new", "reviewing", "proposed", "adopted", "deferred", "rejected"},
    "adoption_decision": {"adopt", "adapt", "copy", "direct_implementation", "defer", "reject"},
    "proposal_needed": {"yes", "no"},
    "approval_required": {"yes", "no"},
}
SCORE_WEIGHTS = {
    "문제 적합성": 20,
    "구조 명확성": 15,
    "검증 가능성": 15,
    "유지보수 신호": 15,
    "흡수 비용": 15,
    "보안/라이선스 리스크": 10,
    "설명 가치": 10,
}
SKIP_FILES = {"README.md", "_template.md"}
FIELD_RE = re.compile(r"^-\s+`([^`]+)`:\s*(.*)$", re.MULTILINE)
SCORE_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d*)\s*\|", re.MULTILINE)


@dataclass
class Finding:
    path: Path
    message: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def candidate_dir(root: Path) -> Path:
    return root / "research" / "reference-candidates"


def parse_fields(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in FIELD_RE.finditer(text)}


def is_blank(value: str) -> bool:
    return value.strip() in {"", "-", "TBD", "todo", "TODO"}


def validate_fields(path: Path, fields: dict[str, str], findings: list[Finding]) -> None:
    for field in REQUIRED_FIELDS:
        if field not in fields:
            findings.append(Finding(path, f"missing field `{field}`"))
            continue
        if is_blank(fields[field]):
            findings.append(Finding(path, f"field `{field}` is blank"))
    for field, allowed in ALLOWED_VALUES.items():
        value = fields.get(field)
        if value and value not in allowed:
            findings.append(
                Finding(
                    path,
                    f"field `{field}` has invalid value `{value}`; expected one of {sorted(allowed)}",
                )
            )


def validate_lists(path: Path, text: str, findings: list[Finding]) -> None:
    for heading in (
        "useful_patterns",
        "what_to_copy_conceptually",
        "what_not_to_copy",
        "target_files_or_areas",
        "files_to_change",
        "sources",
    ):
        marker = f"- `{heading}`:"
        index = text.find(marker)
        if index == -1:
            findings.append(Finding(path, f"missing list field `{heading}`"))
            continue
        tail = text[index + len(marker) :]
        next_field = tail.find("\n- `")
        block = tail if next_field == -1 else tail[:next_field]
        if not re.search(r"^\s+-\s+\S", block, re.MULTILINE):
            findings.append(Finding(path, f"list field `{heading}` has no items"))


def has_list_items(text: str, heading: str) -> bool:
    marker = f"- `{heading}`:"
    index = text.find(marker)
    if index == -1:
        return False
    tail = text[index + len(marker) :]
    next_field = tail.find("\n- `")
    block = tail if next_field == -1 else tail[:next_field]
    return re.search(r"^\s+-\s+\S", block, re.MULTILINE) is not None


def validate_copy_decision(path: Path, text: str, fields: dict[str, str], findings: list[Finding]) -> None:
    if fields.get("adoption_decision") != "copy":
        return
    if not has_list_items(text, "what_to_copy_directly"):
        findings.append(Finding(path, "copy decision requires list field `what_to_copy_directly` with items"))
    copy_boundary = fields.get("copy_boundary", "")
    if is_blank(copy_boundary):
            findings.append(Finding(path, "copy decision requires non-blank field `copy_boundary`"))


def validate_direct_implementation(path: Path, fields: dict[str, str], findings: list[Finding]) -> None:
    if fields.get("adoption_decision") != "direct_implementation":
        return
    reason = fields.get("direct_implementation_reason", "")
    if is_blank(reason) or reason.lower() in {"not applicable", "n/a"}:
        findings.append(Finding(path, "direct_implementation decision requires non-blank field `direct_implementation_reason`"))


def validate_sources(path: Path, text: str, findings: list[Finding]) -> None:
    marker = "- `sources`:"
    index = text.find(marker)
    if index == -1:
        findings.append(Finding(path, "missing list field `sources`"))
        return
    tail = text[index + len(marker) :]
    next_field = tail.find("\n- `")
    block = tail if next_field == -1 else tail[:next_field]
    source_lines = [line.strip()[2:].strip() for line in block.splitlines() if line.strip().startswith("- ")]
    if not source_lines:
        findings.append(Finding(path, "list field `sources` has no items"))
        return
    required = ("path", "kind", "evidence", "hash_or_line_ref")
    for offset, line in enumerate(source_lines, start=1):
        missing = [field for field in required if f'"{field}"' not in line and f"'{field}'" not in line]
        if missing:
            findings.append(Finding(path, f"sources item {offset} missing: {', '.join(missing)}"))


def validate_scores(path: Path, text: str, findings: list[Finding]) -> None:
    seen: dict[str, tuple[int, int]] = {}
    for match in SCORE_RE.finditer(text):
        criterion = match.group(1).strip()
        weight = int(match.group(2))
        score_text = match.group(3).strip()
        if criterion not in SCORE_WEIGHTS and criterion != "합계":
            continue
        if not score_text:
            findings.append(Finding(path, f"score for `{criterion}` is blank"))
            continue
        score = int(score_text)
        seen[criterion] = (weight, score)
    for criterion, expected_weight in SCORE_WEIGHTS.items():
        if criterion not in seen:
            findings.append(Finding(path, f"missing score row `{criterion}`"))
            continue
        weight, score = seen[criterion]
        if weight != expected_weight:
            findings.append(
                Finding(path, f"score row `{criterion}` has weight {weight}, expected {expected_weight}")
            )
        if score < 0 or score > expected_weight:
            findings.append(
                Finding(path, f"score row `{criterion}` score {score} outside 0..{expected_weight}")
            )
    if "합계" not in seen:
        findings.append(Finding(path, "missing score row `합계`"))
        return
    total_weight, total_score = seen["합계"]
    expected_total = sum(seen[criterion][1] for criterion in SCORE_WEIGHTS if criterion in seen)
    if total_weight != 100:
        findings.append(Finding(path, f"score row `합계` has weight {total_weight}, expected 100"))
    if total_score != expected_total:
        findings.append(
            Finding(path, f"score row `합계` is {total_score}, expected {expected_total}")
        )


def candidate_files(root: Path) -> list[Path]:
    directory = candidate_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.md")
        if path.name not in SKIP_FILES and not path.name.startswith(".")
    )


def validate(root: Path) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files = candidate_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8")
        fields = parse_fields(text)
        validate_fields(path, fields, findings)
        validate_lists(path, text, findings)
        validate_copy_decision(path, text, fields, findings)
        validate_direct_implementation(path, fields, findings)
        validate_sources(path, text, findings)
        validate_scores(path, text, findings)
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
        print("reference candidate findings:")
        for finding in findings:
            rel = finding.path.relative_to(root).as_posix()
            print(f"  ERROR {rel}: {finding.message}")
        print(f"checked {count} candidate card(s), {len(findings)} error(s)")
        return 1
    print(f"reference candidates OK: {count} candidate card(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
