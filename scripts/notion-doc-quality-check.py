#!/usr/bin/env python3
"""Check whether a Notion documentation draft is feature-centered enough.

The script reads one or more Markdown files, or stdin with ``-``. It is meant
for drafts before they are copied into Notion. It does not contact Notion.
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


MIN_BODY_CHARS = 400
PATH_PATTERN = re.compile(
    r"(`[^`]+[/\\][^`]+`|(?:^|\s)(?:docs|src|scripts|runtime|server|web|tests|output)[/\\][^\s,;:)]+)",
    re.MULTILINE,
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


REQUIRED_GROUPS = {
    "definition": ("한 문장 정의", "목적", "정의"),
    "problem": ("사용자가 겪는 문제", "문제", "왜 읽어야 하는가"),
    "scope": ("무엇을 하는가", "무엇을 해결하는가", "해결 범위"),
    "why": ("왜 필요한가", "필요성"),
    "usage": ("사용 시점", "언제 사용하는가", "언제 쓰는가"),
    "flow": ("어떻게 동작하는가", "동작 흐름", "흐름"),
    "io": ("입력과 출력", "입력/출력", "입출력"),
    "success": ("성공 상태", "성공 기준"),
    "failure": ("실패 신호", "실패 기준"),
    "decision": ("기능 추가/수정", "판단 기준", "추가/수정/보류"),
}


@dataclass
class Finding:
    level: str
    detail: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _headings(text: str) -> list[str]:
    return [match.group(2).strip() for match in HEADING_PATTERN.finditer(text)]


def _has_group(headings: list[str], aliases: tuple[str, ...]) -> bool:
    normalized_headings = [_normalize(heading) for heading in headings]
    for alias in aliases:
        normalized_alias = _normalize(alias)
        if any(normalized_alias in heading for heading in normalized_headings):
            return True
    return False


def check_text(name: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    body = text.strip()
    headings = _headings(body)

    if len(body) < MIN_BODY_CHARS:
        findings.append(
            Finding(
                "error",
                f"body is {len(body)} chars; feature docs should be at least {MIN_BODY_CHARS} chars",
            )
        )

    if not headings:
        findings.append(Finding("error", "no Markdown headings found"))
    else:
        first_heading = headings[0]
        if re.search(r"\b\d{4}[-./]\d{2}[-./]\d{2}\b", first_heading):
            findings.append(
                Finding(
                    "warn",
                    "first heading starts from a date; prefer the feature or decision topic",
                )
            )
        if _normalize(first_heading) in {"요약", "summary", "주요구현", "검증"}:
            findings.append(
                Finding(
                    "warn",
                    "first heading is generic; open with feature purpose or user problem",
                )
            )

    for group_name, aliases in REQUIRED_GROUPS.items():
        if not _has_group(headings, aliases):
            findings.append(
                Finding(
                    "error",
                    f"missing section group '{group_name}' ({' / '.join(aliases)})",
                )
            )

    path_matches = PATH_PATTERN.findall(body)
    path_count = len(path_matches)
    bullet_count = len(re.findall(r"^\s*[-*]\s+", body, re.MULTILINE))
    if path_count >= 8 and path_count >= max(4, bullet_count // 2):
        findings.append(
            Finding(
                "warn",
                "many path-like references detected; keep paths in '구현 연결 정보'",
            )
        )

    if "구현 연결 정보" in body:
        before_impl = body.split("구현 연결 정보", 1)[0]
        early_paths = len(PATH_PATTERN.findall(before_impl))
        if early_paths >= 5:
            findings.append(
                Finding(
                    "warn",
                    "path-like references appear before '구현 연결 정보'; move details later",
                )
            )

    if "기능 영역" in body and not re.search(r"^#{2,3}\s+.+", body, re.MULTILINE):
        findings.append(
            Finding(
                "warn",
                "multiple feature areas are mentioned but the body is not split into sections",
            )
        )

    return findings


def read_input(path_text: str) -> tuple[str, str]:
    if path_text == "-":
        return "stdin", sys.stdin.read()
    path = Path(path_text)
    return path.as_posix(), path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "drafts",
        nargs="+",
        help="Markdown draft path(s), or '-' to read stdin.",
    )
    args = parser.parse_args()

    had_error = False
    for draft in args.drafts:
        name, text = read_input(draft)
        findings = check_text(name, text)
        errors = [finding for finding in findings if finding.level == "error"]
        warns = [finding for finding in findings if finding.level == "warn"]
        if errors:
            had_error = True
        if not findings:
            print(f"{name}: OK")
            continue
        print(f"{name}:")
        for finding in errors:
            print(f"  ERROR {finding.detail}")
        for finding in warns:
            print(f"  WARN  {finding.detail}")

    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
