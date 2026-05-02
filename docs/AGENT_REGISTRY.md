# 에이전트 레지스트리

## 한 문장 정의

에이전트 레지스트리는 반복 투입할 에이전트를 이름, 역할, 권한, 상태, 목표 계보로 관리하는 운영 목록입니다.

## 무엇을 하는가

이 문서는 에이전트를 “그때그때 부르는 도우미”가 아니라 운영 자산으로 관리합니다. 어떤 에이전트가 어떤 일을 맡을 수 있는지, 어떤 범위를 읽고 쓸 수 있는지, 언제 승인이 필요한지, 실행 후 무엇을 기록해야 하는지를 정합니다.

## 왜 필요한가

에이전트가 많아질수록 누가 무엇을 책임지는지 흐려집니다. 권한 없이 쓰기 작업을 하거나, 같은 작업을 중복 수행하거나, 목표와 무관한 탐색을 계속할 위험도 커집니다. 레지스트리는 에이전트 투입을 추적 가능한 결정으로 만들기 위해 필요합니다.

## 어떻게 동작하는가

에이전트를 반복적으로 사용하려면 먼저 역할과 책임을 정합니다. 그런 다음 읽기 범위, 쓰기 범위, 사용할 수 있는 도구, 승인 필요 조건, 실행 기록 방식을 정합니다. 실행할 때는 현재 작업이 어떤 상위 목표와 연결되는지 목표 계보를 남깁니다.

기본 역할은 사용자-facing으로 세 가지입니다. 반복 투입할 에이전트 정의의 canonical 위치는 `agents/`이며, `scripts/convert.py`가 `.codex/agents/`와 `.claude/agents/`를 재생성합니다.

| 역할 | 하는 일 | 투입 기준 |
| --- | --- | --- |
| planner/researcher | 자연어 goal을 `agent-flow start`의 mode와 next_command로 번역하고, reference-first 조사와 흡수 방식 판단을 묶어서 수행합니다. | 목표가 모호하거나 외부 사례를 먼저 봐야 할 때 |
| implementer | 승인된 범위 안에서 코드를 수정하거나 산출물을 만듭니다. | 쓰기 범위와 검증 방법이 명확할 때 |
| validator | 독립적으로 결과를 확인하고 실패 유형을 분류합니다. | 구현 후 품질과 회귀 위험을 확인해야 할 때 |

## 결과는 무엇인가

레지스트리를 사용하면 다음 정보를 항상 추적할 수 있습니다.

- 어떤 에이전트가 어떤 역할을 맡는지
- 어떤 범위까지 읽고 쓸 수 있는지
- 어떤 경우에 승인이 필요한지
- 어떤 상위 목표 때문에 실행됐는지
- 실행 기록이 어디에 남는지

## 현재 등록된 기본 역할

| 에이전트 | 역할 | 상태 | 기본 사용 상황 |
| --- | --- | --- | --- |
| strategy-planner | planner/researcher | active | 구조 설계, 계획, 최종 검토 |
| codebase-explorer | planner/researcher | active | 읽기 전용 조사와 맥락 수집 |
| implementation-worker | implementer | draft | 명확한 쓰기 범위가 있는 구현 |
| independent-validator | validator | active | 구현 후 독립 검증과 리스크 확인 |

## 내부 specialist 후보

사용자-facing 팀은 위 3단계를 유지합니다. 아래 specialist는 사용자가 직접 부르는 공개 명령이 아니라 planner가 좁은 질문을 위임할 때만 쓰는 내부 후보입니다.

| specialist | 상위 역할 | 기본 사용 상황 |
| --- | --- | --- |
| build-error-resolver | implementer | build/typecheck/test 실패의 최소 수정 |
| security-reviewer | validator | `security-scan`, permission, secret, copied-source finding 검토 |
| reference-reviewer | planner/researcher | reference 후보 비교와 source-backed 흡수 근거 작성 |
| docs-sync-auditor | validator | docs/catalog/codemap/wiki drift 점검 |
| closeout-validator | validator | verify, quality-gate, completion evidence 독립 확인 |

## 에이전트 팀 운영 모델

새 프로젝트나 큰 기능은 다음 팀 흐름을 기본으로 둡니다. 핵심은 구현 에이전트가 먼저 뛰어들기 전에, planner/researcher가 “무엇을 재사용할 수 있는지”를 정리하고, validator가 마지막에 독립적으로 닫는 것입니다.

| 단계 | 담당 역할 | 기본 산출물 | 다음 단계 조건 |
| --- | --- | --- | --- |
| 1. planner/researcher | strategy-planner + codebase-explorer | 문제 정의, 후보 카드, dependency/wrapper/partial_copy/concept_only/direct_implementation 판단 | 사용자 승인 또는 명시적 예외 |
| 2. implementer | implementation-worker | 승인된 파일 변경, copy ledger 필요 시 기록 | 로컬 검증 통과 |
| 3. validator | independent-validator | 실패/회귀/보안/증거 검토 | closeout evidence 기록 |

### 기본 위임 규칙

- 탐색 에이전트는 읽기 전용입니다. clone이나 쓰기 작업은 `runtime/external-repos/`와 후보 카드/제안서 범위로 제한합니다.
- 구현 에이전트는 명시된 write scope 밖을 수정하지 않습니다.
- 검증 에이전트는 구현과 같은 파일을 고치지 않고, 실패 증거와 재현 명령을 먼저 남깁니다.
- 같은 문제를 여러 에이전트에게 중복 배정하지 않습니다. 병렬화는 후보 조사, 리스크 조사, 검증처럼 서로 독립인 질문에만 사용합니다.
- `direct_implementation`은 마지막 선택입니다. 후보 분석에서 dependency, wrapper, partial_copy, concept_only가 부적합한 이유를 먼저 남겨야 합니다.

### 새 프로젝트 기본 프롬프트 연결

새 프로젝트에서 사용자가 주제만 준 경우 운영자는 다음 순서로 진행합니다.

1. `AGENTS.md`와 `docs/PROJECT_PROFILE.md`를 읽습니다.
2. `python3 scripts/agent-flow.py start --goal "<사용자 자연어 목표>" --format json`로 열린 결정과 다음 추천 액션을 확인합니다. 이 판단 규칙은 `scripts/catalog.yaml`의 `routing.modes`와 `write_policy`가 단일 소스입니다.
3. `agent-flow start`가 반환한 `research --auto --goal "<사용자 자연어 목표>"` 명령으로 외부 후보를 먼저 다룹니다.
4. 후보 카드와 dry-run proposal을 만든 뒤 `agent-flow.py decide`로 사용자 결정을 기록합니다.
5. 승인된 범위만 구현하고 `agent-flow.py closeout`으로 검증과 evidence 기록을 묶어 닫습니다.

`start`의 `suggested_questions`와 `build_intake`는 에이전트가 사용자와 대화할 때 참고하는 질문 후보입니다. 스크립트가 사용자를 대신해 질문하거나 입력을 받는 기능이 아니며, 사용자가 셸 명령을 직접 실행해야 한다는 뜻도 아닙니다. `write_policy`가 `read_only`인 흐름은 조사/보고에 머물고, `manual_work_required`는 구현 범위 확인과 plan 작성 후 쓰기 작업으로 넘어가며, `write_with_confirmation`은 append-only 증거나 승인된 산출물처럼 명시적 종료 단계에서만 사용합니다. `research --auto --goal`의 `reference_candidates`는 자동 선택을 설명하는 top 후보 목록이고, named reference는 후보 카드가 이미 있어도 재사용 후보로 먼저 노출합니다. 라우팅 문구나 질문을 바꿀 때는 Python 코드보다 `scripts/catalog.yaml`을 먼저 수정합니다.

전문가에게 위임할 때는 `config/agent-team.yaml`을 canonical registry로 보고, `scripts/agent-brief.py`로 brief를 만든 뒤 전달합니다. brief에는 role, goal, allowed scope, write policy, forbidden actions, recommended checks가 포함되어야 하며, specialist는 public command를 직접 확장하지 않습니다.

`agent-flow run --goal`은 future candidate입니다. 자동 실행 범위가 커지기 전까지는 `start`가 추천하고 에이전트가 단계별로 실행하는 구조를 유지합니다.

## 기능 추가/수정 판단 기준

새 에이전트를 등록하기 전에 다음을 확인합니다.

- 같은 역할을 기존 에이전트가 수행할 수 없는가?
- 반복 실행될 만큼 자주 필요한가?
- 읽기 범위와 쓰기 범위가 명확한가?
- 목표 계보를 기록할 수 있는가?
- 검증 또는 완료 기준이 있는가?

기존 에이전트를 수정해야 하는 경우는 다음과 같습니다.

- 역할은 맞지만 권한이나 쓰기 범위가 실제 사용과 맞지 않을 때.
- 목표 계보나 실행 로그가 부족할 때.
- 새로운 작업 유형이 기존 역할의 하위 책임으로 들어갈 수 있을 때.

## 목표 계보 규칙

위임되거나 반복되는 에이전트 작업은 목표 계보를 포함해야 합니다. 목표 계보는 현재 작업이 어떤 워크플로와 프로젝트 목표에 연결되는지 보여주는 한 줄 설명입니다. 작업 시작 시 사용자에게도 짧게 보여주면 긴 세션에서 “왜 하는가”를 잃지 않습니다.

예시:

```text
문서화 구조 개선 중 -> 프로젝트 운영 판단 가능성 개선 -> 공용 AI 운영 시스템 신뢰도 향상
```

## 구현 연결 정보

- 에이전트 정의: `agents/`
- generated 에이전트 산출물: `.codex/agents/`, `.claude/agents/`
- 팀/전문가 registry: `config/agent-team.yaml`
- 권한 기준: `codex/rules/AGENT_PERMISSIONS.md`
- 워크플로 카탈로그: `docs/WORKFLOW_CATALOG.md`
- 에이전트 실행 로그: `runtime/agent-runs.jsonl`
