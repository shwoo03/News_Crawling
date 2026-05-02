# Codex 에이전트 역할 규칙

## 한 문장 정의

이 문서는 Codex 작업을 전략, 탐색, 구현, 검증 역할로 나누고, 각 역할이 목표 계보와 권한을 잃지 않게 만드는 규칙입니다.

## 무엇을 하는가

작업이 넓거나 반복되거나 병렬 조사가 필요할 때 메인 에이전트가 모든 일을 직접 처리하지 않고 역할별 에이전트로 나눌 수 있게 합니다. 각 에이전트는 이름, 설명, 도구, 권한, 예산, 상태를 가진 운영 단위입니다.

## 왜 필요한가

에이전트를 무작정 늘리면 중복 조사, 쓰기 충돌, 목표 이탈이 생깁니다. 반대로 모든 일을 한 컨텍스트에서 처리하면 긴 작업에서 맥락이 과도하게 커집니다. 역할 규칙은 병렬성은 얻고 책임 혼란은 줄이기 위해 필요합니다.

## 어떻게 동작하는가

에이전트 파일은 먼저 짧은 메타데이터로 발견됩니다. 자세한 본문은 실제로 해당 역할이 필요할 때만 읽습니다. 반복 사용되는 에이전트는 에이전트 레지스트리에 등록하고, 실행 시 목표 계보와 결과를 로그에 남깁니다.

기본 역할은 다음과 같습니다.

| 역할 | 사용 상황 | 결과 |
| --- | --- | --- |
| 전략 | 구조 설계, 트레이드오프, 계획, 최종 검토 | 결정 요약과 실행 계획 |
| 탐색 | 읽기 전용 코드베이스 또는 도메인 조사 | 제한된 발견 사항 |
| 구현 | 명확한 소유 범위가 있는 변경 | 파일 변경과 검증 메모 |
| 검증 | 독립 테스트와 리스크 확인 | 발견 사항, 위험도, 통과/실패 증거 |

## 결과는 무엇인가

이 규칙을 적용하면 다음 상태를 얻습니다.

- 에이전트가 왜 투입됐는지 목표 계보로 설명됩니다.
- 쓰기 범위가 명확합니다.
- 급한 블로킹 작업과 병렬 사이드 작업을 구분합니다.
- 검증 역할이 구현 역할과 분리됩니다.
- 반복 에이전트는 레지스트리와 실행 로그로 추적됩니다.

## 위임 규칙

- 다음 행동이 바로 막혀 있으면 보통 메인 에이전트가 직접 처리합니다.
- 병렬로 진행해도 되는 구체적이고 독립적인 작업만 위임합니다.
- 구현 에이전트에는 명확한 파일 또는 하위 시스템 소유 범위를 줍니다.
- 모든 위임 작업에는 목표 계보를 포함합니다.
- 작업 시작 시 목표 계보를 한 문장으로 사용자에게 보여줍니다.
- 구현 에이전트에게 다른 작업자가 있을 수 있음을 알리고, 관련 없는 변경을 되돌리지 않게 합니다.
- 같은 작업을 여러 에이전트에게 중복 위임하지 않습니다.

## 에이전트 frontmatter 스키마

`codex/agents/<agent>.md` 파일은 다음 YAML frontmatter를 사용합니다. `scripts/verify-skeleton.py`는 `name`과 `description`이 있는지 확인합니다. 나머지 필드도 아래 규칙을 지켜야 런타임에서 오동작이 없습니다.

| 필드 | 필수 | 허용 값 | 설명 |
| --- | --- | --- | --- |
| `name` | ✅ | 소문자 하이픈 문자열 | 파일 이름과 일치해야 합니다 |
| `description` | ✅ | 한 문장 | 언제 이 에이전트를 부르는지 |
| `tools` | 권장 | 문자열 배열 | 사용할 도구 카테고리 (예: `[read, search]`) |
| `model` | 권장 | `strongest-available`, `fast-capable`, `coding-optimized` 등 | 선호 모델군 |
| `permissions.read` | 권장 | 경로 또는 범주 배열 | 읽기 허용 범위 |
| `permissions.write` | 권장 | 경로 또는 범주 배열 (빈 배열 허용) | 쓰기 허용 범위. 비우면 읽기 전용 |
| `permissions.approval_required` | 선택 | 사람 승인 트리거 목록 | 무엇을 바꾸려면 승인이 필요한지 |
| `status` | ✅ | `active`, `draft`, `deprecated`, `archived` | 운영 상태 |

`status: draft`인 에이전트는 사용자 명시 승인 없이 호출하지 않습니다. active가 되려면 워크플로 카탈로그의 활성화 기준을 통과해야 합니다.

토큰·시간·주기 예산 필드는 제거했습니다. Codex와 Claude Code가 런타임에 직접 강제하지 않는 숫자를 frontmatter에 두면 "선언 있음, 강제 없음" 격차만 생기기 때문입니다. 예산이 필요한 프로젝트는 `docs/PROJECT_OPERATING_PLAN.md`에 프로젝트별로 정의합니다.

## 프롬프트 템플릿

```text
Role:
Lineage:
Objective:
Context:
Scope:
Non-goals:
Expected output:
Length limit:
Verification required:
```

`Lineage`에는 현재 작업이 어떤 워크플로와 프로젝트 목표에 연결되는지 한 줄로 적습니다.

예시:

```text
Lineage: Notion 문서 구조 개선 -> 기능 결정 가능성 개선 -> 공용 AI 운영 시스템 신뢰도 향상
```

## 기능 추가/수정 판단 기준

새 에이전트 역할은 다음 조건을 만족할 때만 추가합니다.

- 기존 역할로는 책임이 모호합니다.
- 반복 사용 가능성이 있습니다.
- 입력, 출력, 권한, 검증 기준이 분리됩니다.
- 목표 계보를 기록할 수 있습니다.

역할 설명이 부족해서 사용자가 이해하지 못하는 경우에는 새 에이전트보다 기존 설명 수정이 우선입니다.

## 에이전트 호출 방법

메인 에이전트는 다음 네 파일을 참고해 역할을 선택합니다. 호출은 "해당 프롬프트 템플릿을 채워 서브-에이전트 컨텍스트로 전달"하는 방식이며, Codex/Claude Code 모두 서브-에이전트 호출 시 동일하게 사용합니다.

| 상황 | 읽을 파일 | 예시 트리거 문구 |
| --- | --- | --- |
| 구조 설계·트레이드오프·계획 | `codex/agents/strategy-planner.md` | "strategy-planner 역할로 X를 계획해줘" |
| 읽기 전용 조사·탐색 | `codex/agents/codebase-explorer.md` | "codebase-explorer 역할로 X 위치를 찾아줘" |
| 배정된 범위 구현 | `codex/agents/implementation-worker.md` | "implementation-worker 역할로 파일 X만 수정해줘" |
| 구현 후 독립 검증 | `codex/agents/independent-validator.md` | "independent-validator 역할로 수용 기준을 확인해줘" |

호출 시 최소 포함 정보:

- Role: 위 네 이름 중 하나.
- Lineage: 이번 작업이 연결되는 상위 목표 (한 줄).
- Scope: 읽기/쓰기 허용 경로.
- Expected output: 해당 에이전트 파일의 "Default output" 섹션 참고.

실행이 끝나면 `runtime/agent-runs.jsonl`에 한 줄을 append합니다. 필수 필드는 `docs/RUNTIME_EVENT_SCHEMA.md` 참고 (`ts`, `event`, `agent`, `workflow`, `project`, `status`, `goal_lineage`, `artifacts`).

## 스키마 드리프트 주의

frontmatter의 `status`는 현재 런타임에서 강제로 읽히지 않습니다. 사람이 레지스트리를 업데이트할 때 참고하는 운영 표식이며, 자동화 대상이 되면 이 문서에 writer를 명시해야 합니다. (직전 라운드에서 미사용 `heartbeat`, `parent_goal` 필드는 제거했습니다.)

## 구현 연결 정보

- 에이전트 레지스트리: `docs/AGENT_REGISTRY.md`
- 권한 기준: `codex/rules/AGENT_PERMISSIONS.md`
- 실행 로그: `runtime/agent-runs.jsonl`
- 실행 로그 스키마: `docs/RUNTIME_EVENT_SCHEMA.md`
