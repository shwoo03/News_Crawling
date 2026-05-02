#!/usr/bin/env python3
"""Create a reference-adoption dry-run proposal draft from a candidate card.

This is an agent-facing helper. By default it prints the generated draft and
the suggested output path. Pass --write when the agent is intentionally
creating the proposal file.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


FIELD_RE = re.compile(r"^-\s+`([^`]+)`:\s*([^\r\n]*?)\r?$", re.MULTILINE)
LIST_FIELD_RE = re.compile(r"^-\s+`([^`]+)`:\s*$", re.MULTILINE)
SAFE_NAME_RE = re.compile(r"[^a-z0-9]+")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def today() -> str:
    return datetime.now().date().isoformat()


def parse_fields(text: str) -> dict[str, str]:
    return {match.group(1): clean_inline_code(match.group(2).strip()) for match in FIELD_RE.finditer(text)}


def clean_inline_code(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`") and stripped.count("`") == 2:
        return stripped[1:-1].strip()
    return stripped


def parse_list_field(text: str, field: str) -> list[str]:
    marker = f"- `{field}`:"
    index = text.find(marker)
    if index == -1:
        return []
    tail = text[index + len(marker) :]
    next_field = tail.find("\n- `")
    block = tail if next_field == -1 else tail[:next_field]
    items: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 2:
            items.append(clean_inline_code(stripped[2:].strip()))
    return items


def slugify(value: str) -> str:
    lowered = value.lower()
    slug = SAFE_NAME_RE.sub("-", lowered).strip("-")
    return slug or "candidate"


def infer_output_path(root: Path, candidate: Path, fields: dict[str, str], topic: str | None) -> Path:
    name = fields.get("name") or candidate.stem
    topic_slug = slugify(topic or fields.get("next_action") or "proposal")
    return root / "runtime" / "proposals" / "reference-adoption" / f"{today()}-{slugify(name)}-{topic_slug}.md"


def bullet_lines(items: list[str], fallback: str) -> str:
    if not items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in items)


def generate(root: Path, candidate: Path, topic: str | None) -> tuple[Path, str]:
    text = candidate.read_text(encoding="utf-8")
    fields = parse_fields(text)
    name = fields.get("name") or candidate.stem
    output_path = infer_output_path(root, candidate, fields, topic)
    candidate_rel = candidate.relative_to(root).as_posix()
    target_files = parse_list_field(text, "target_files_or_areas")
    useful_patterns = parse_list_field(text, "what_to_copy_conceptually") or parse_list_field(text, "useful_patterns")
    direct_copy = parse_list_field(text, "what_to_copy_directly")
    not_to_copy = parse_list_field(text, "what_not_to_copy")
    sources = parse_list_field(text, "sources")
    reference_task_id = fields.get("reference_task_id", "")
    behavior_change = fields.get("behavior_change") or fields.get("next_action") or "후보 카드의 적용 후보를 검토해 작은 운영 변경으로 번역한다."
    validation_plan = fields.get("validation_plan") or "`python scripts/verify-skeleton.py`, `python scripts/validate-reference-candidates.py`, `python scripts/validate-reference-proposals.py`, `python scripts/list-open-questions.py --count`"
    stop_condition = fields.get("rollback_or_stop_condition") or "특정 외부 도구 도입처럼 읽히거나 승인 범위를 넘어가면 중단한다."
    license_text = fields.get("license", "")
    adoption_decision = fields.get("adoption_decision", "adapt")
    absorption_mode = "concept_only"
    if adoption_decision == "adopt":
        absorption_mode = "dependency"
    elif adoption_decision == "copy":
        absorption_mode = "partial_copy"
    elif "GPL" in license_text.upper():
        absorption_mode = "concept_only"

    body = f"""# {name} 후보 기반 {topic or 'reference adoption'} 제안

## 상태

- `status`: proposed
- `created_at`: {today()}
- `candidate_card`: `{candidate_rel}`
- `proposal_type`: reference_adoption_dry_run
- `reference_task_id`: {reference_task_id or 'not queued'}
- `approval_required`: yes
- `decision_source`:

## 한 문장 정의

{name} 후보에서 확인한 유용한 패턴을 이 스켈레톤에 맞는 작은 운영 변경으로 번역할지 검토하는 dry-run 제안입니다.

이 제안서는 후보를 검토하는 초안입니다. 특정 도구나 프레임워크를 기본 의존성으로 도입한다는 뜻이 아닙니다.

## 근거

후보 카드의 문제 정의:

```text
{fields.get('problem_statement', '후보 카드의 문제 정의를 확인해야 합니다.')}
```

후보 카드의 기대 가치:

```text
{fields.get('expected_value', '후보 카드의 기대 가치를 확인해야 합니다.')}
```

Source-backed evidence:

{bullet_lines(sources, 'candidate card did not provide structured sources')}

## 적용하지 않을 것

{bullet_lines(not_to_copy, '후보 저장소나 프레임워크를 통째로 도입하지 않는다.')}

## 모듈형 흡수 판단

- `absorption_mode`: {absorption_mode}
- `recommended_mode`: 후보 카드의 `adoption_decision`은 `{adoption_decision}`입니다. 기본 제안은 외부 후보의 핵심 패턴을 작게 흡수하고, `copy` 결정이면 승인된 범위의 partial copy를 검토합니다.
- `reuse_boundary`: 후보 원본은 `runtime/external-repos/`에서 분석하고, 장기 반영은 문서, 규칙, 스킬, 스크립트 중 승인된 범위로 제한합니다.
- `direct_implementation_reason`: 직접 구현이 필요하면 기존 오픈소스를 쓰지 못하는 이유를 이 제안서에 남깁니다. 이유가 없으면 직접 구현보다 dependency, wrapper, partial copy, concept-only 중 하나를 우선 검토합니다.
- `copy_boundary`: {('private local only; source/license/revision copied scope must be recorded before redistribution review' if adoption_decision == 'copy' else 'not applicable')}

흡수 방식 판단:

- 의존성 사용: 후보를 그대로 설치해 쓸 수 있는지 검토합니다.
- wrapper 사용: 후보의 CLI, API, 모듈 일부를 얇은 adapter로 감쌀 수 있는지 검토합니다.
- 일부 코드 복사: 개인 로컬 프로젝트에서는 라이선스가 채택 차단 기준이 아니지만, 출처와 라이선스, 확인한 revision, 복사 범위를 기록하고 공개/재배포 전에는 다시 검토합니다.
- 개념 번역: 코드보다 운영 원칙이나 구조만 필요한지 검토합니다.
- 직접 구현: 기존 후보를 쓰지 않는 이유가 명확할 때만 선택합니다.

## 제안 변경

### 1. 후보 패턴을 운영 규칙으로 번역

대상: {', '.join(f'`{item}`' for item in target_files) if target_files else '`TBD`'}

추가할 내용:

{bullet_lines(useful_patterns, '후보 카드의 유용한 패턴을 작게 번역한다.')}

직접 복사 후보:

{bullet_lines(direct_copy, '직접 복사할 코드는 아직 지정하지 않았다.')}

예상 문구 방향:

```text
{behavior_change}
```

## 기대 효과

- 외부 후보의 좋은 점을 특정 도구 도입이 아니라 운영 원칙으로 검토할 수 있습니다.
- 실제 반영 전 변경 범위와 검증 방법을 사용자가 채팅으로 승인하거나 거절할 수 있습니다.

## 위험

- 후보 이름이 특정 도구 도입 계획처럼 보일 수 있습니다.
- 적용 범위가 넓어지면 스켈레톤이 불필요하게 복잡해질 수 있습니다.

완화:

- 승인 전에는 실제 운영 문서를 수정하지 않습니다.
- 제안서에 적용하지 않을 것을 명시합니다.

## 검증 계획

승인 후 실제 반영 작업에서는 다음을 실행합니다.

```powershell
python scripts/verify-skeleton.py
python scripts/validate-reference-candidates.py
python scripts/validate-reference-proposals.py
python scripts/list-open-questions.py --count
```

후보 카드의 검증 계획:

```text
{validation_plan}
```

## 롤백 또는 중단 조건

- {stop_condition}

## 승인 후 실제 변경 범위

{bullet_lines(target_files, 'TBD')}

## 최종 결정 기록

- `decision`: pending
- `decided_at`:
- `decided_by`:
- `decision_source`:
- `applied_in`:
- `validation_result`:
"""
    return output_path, body


def enqueue_review(root: Path, proposal: Path, title: str, target_files: list[str]) -> str:
    script = root / "scripts" / "review-queue.py"
    if not script.exists():
        return ""
    command = [
        sys.executable,
        str(script),
        "--root",
        str(root),
        "add",
        "--type",
        "reference-adoption",
        "--title",
        f"Reference adoption approval: {title}",
        "--description",
        "Review the generated reference adoption proposal before any absorption or implementation.",
        "--source-path",
        proposal.relative_to(root).as_posix(),
        "--option",
        "accepted",
        "--option",
        "rejected",
        "--option",
        "deferred",
        "--json",
    ]
    command.extend(["--affected-path", proposal.relative_to(root).as_posix()])
    for item in target_files:
        command.extend(["--affected-path", item])
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
    except subprocess.SubprocessError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, help="Path to a candidate card.")
    parser.add_argument("--topic", default=None, help="Short proposal topic for the title and filename.")
    parser.add_argument("--output", default=None, help="Optional output path.")
    parser.add_argument("--write", action="store_true", help="Write the proposal file instead of printing it.")
    parser.add_argument("--root", default=None, help="Project root (defaults to this script's repository root).")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root()
    candidate = Path(args.candidate)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        print(f"candidate must be inside project root {root}: {candidate}", file=sys.stderr)
        return 2
    if not candidate.is_file():
        print(f"candidate not found: {candidate}", file=sys.stderr)
        return 2

    output_path, body = generate(root, candidate, args.topic)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = root / output_path
        output_path = output_path.resolve()
    try:
        output_path.relative_to(root)
    except ValueError:
        print(f"output must be inside project root {root}: {output_path}", file=sys.stderr)
        return 2

    if args.write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            print(f"refusing to overwrite existing proposal: {output_path}", file=sys.stderr)
            return 1
        output_path.write_text(body, encoding="utf-8")
        print(f"created {output_path.relative_to(root).as_posix()}")
        target_files = parse_list_field(candidate.read_text(encoding="utf-8"), "target_files_or_areas")
        queue_result = enqueue_review(root, output_path, output_path.stem, target_files)
        if queue_result:
            print(f"queued reference adoption review: {queue_result}")
    else:
        print(f"# suggested_output: {output_path.relative_to(root).as_posix()}")
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
