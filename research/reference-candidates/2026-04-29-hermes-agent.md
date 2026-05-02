# Hermes Agent

## 기본 정보

- `name`: Hermes Agent
- `url`: https://github.com/NousResearch/hermes-agent
- `source_type`: repository
- `status`: proposed
- `searched_for`: self-improving agent, learning loop, skills, memory, session search, subagents, multi-environment execution
- `created_at`: 2026-04-29
- `reviewed_at`: 2026-04-29
- `reviewer`: Codex

## 왜 보는가

- `problem_statement`: 이 스켈레톤은 세션 인수인계, 스킬, 활동 로그를 갖고 있지만 새 프로젝트 시작 시 외부 시스템을 먼저 학습하고 모듈형으로 흡수하도록 강제하는 계약은 약하다.
- `why_it_matters`: Hermes Agent는 학습 루프, 스킬 생성, 기억, 과거 대화 검색, 서브에이전트 병렬화, 여러 실행 환경을 하나의 에이전트 운영 제품으로 묶는다.
- `expected_value`: Hermes 자체를 복제하지 않고도 오픈소스 우선 조사, 경험 기반 스킬화, 세션 검색, 반복 작업 자동화, 병렬 에이전트 경계 원칙을 스켈레톤 운영 규칙으로 번역할 수 있다.

## 유용한 패턴

- `useful_patterns`:
  - 경험에서 스킬을 만들고 사용 중 개선하는 closed learning loop.
  - FTS5 기반 세션 검색과 요약으로 이전 대화와 작업을 회수하는 방식.
  - 격리된 서브에이전트로 병렬 작업을 나누는 운영 모델.
  - local, Docker, SSH, Daytona, Singularity, Modal 같은 다중 실행 backend 지원 관점.
- `what_to_copy_conceptually`:
  - 새 프로젝트마다 외부 사례를 먼저 학습하고 반복 패턴은 스킬이나 워크플로로 승격하는 절차.
  - 세션 검색과 활동 로그를 단순 기록이 아니라 다음 실행의 근거로 쓰는 방식.
  - 서브에이전트는 목표 계보와 검증 경계가 있을 때만 사용하는 원칙.
- `what_not_to_copy`:
  - Hermes 런타임, Telegram 인터페이스, Honcho 의존성, 클라우드 실행 backend를 기본 스켈레톤 의존성으로 추가하지 않는다.
  - 모든 프로젝트에 자동 스킬 생성을 강제하지 않는다.
  - 사용자의 개인 기억이나 글로벌 스킬 공간을 스켈레톤이 직접 수정하지 않는다.

## 증거

- `evidence_summary`: README는 Hermes를 built-in learning loop를 가진 self-improving AI agent로 설명하고, agent-curated memory, autonomous skill creation, FTS5 session search, scheduled automation, subagent delegation, multiple terminal backends를 핵심 능력으로 제시한다.
- `local_clone_path`: runtime/external-repos/github.com/NousResearch__hermes-agent
- `checked_revision`: 58a6171bfb0ba2ca10b1b08854511736cd77a623
- `freshness_signal`: 2026-04-29에 GitHub 원본을 shallow clone했고 README와 LICENSE를 확인했다.
- `maintenance_signal`: 공개 저장소이며 Nous Research가 관리하고, README에 문서 사이트, Docker, skills hub, 설치 경로가 유지되어 있다.
- `documentation_signal`: README가 기능 표, 설치 방법, CLI 사용법, docs 링크, import 경로를 제공한다.
- `validation_signal`: clone revision과 MIT license를 확인했다. 이번 P0에서는 개념 후보 카드만 만들고 런타임 코드는 도입하지 않는다.
- `sources`:
  - {"path":"../AI_architecture_references/hermes-agent/README.md","kind":"readme","evidence":"Agent runtime and persistence concepts were reviewed.","hash_or_line_ref":"local-reference"}
  - {"path":"../AI_architecture_references/hermes-agent/tools/session_search_tool.py","kind":"source_file","evidence":"Session search pattern was inspected conceptually.","hash_or_line_ref":"local-reference"}

## 리스크

- `license`: MIT license로 확인했다. 코드 복사는 가능성이 열려 있지만 P0에서는 개념만 참고한다.
- `security_or_privacy_risk`: 기억, 세션 검색, 사용자 모델링을 그대로 도입하면 민감 정보가 장기 저장될 수 있다.
- `maintenance_risk`: Hermes 자체의 빠른 제품 변화가 스켈레톤의 안정적인 운영 계약과 어긋날 수 있다.
- `complexity_risk`: 런타임, 백엔드, 스케줄러, 메시징 인터페이스를 통째로 흡수하면 스켈레톤이 무거워진다.
- `dependency_risk`: 기본 스켈레톤은 외부 패키지 없는 Python 운영 도구를 선호하므로 Hermes 의존성 직접 도입은 부적합하다.
- `fit_risk`: Hermes는 완성형 에이전트 제품이고 이 저장소는 프로젝트별 운영 뼈대이므로 개념만 번역해야 한다.

## 적용 후보

- `applies_to`: docs | rules | skills | runtime
- `target_files_or_areas`:
  - AGENTS.md
  - docs/REFERENCE_DISCOVERY_WORKFLOW.md
  - docs/WORKFLOW_CATALOG.md
  - runtime/state/session-handoff.md
- `adoption_decision`: adapt
- `decision_reason`: 학습 루프와 스킬/세션 검색/서브에이전트 패턴은 목표에 직접 맞지만 Hermes 런타임 전체 도입은 현재 스켈레톤 경량성 원칙과 맞지 않는다.
- `next_action`: 오픈소스 우선 조사와 경험 기반 스킬화 원칙을 AGENTS와 프로젝트 프로필 템플릿에 반영하고, 이후 dry-run 제안으로 세션 검색/스킬 승격 규칙을 검토한다.

## 점수

| 기준 | 배점 | 점수 | 근거 |
| --- | ---: | ---: | --- |
| 문제 적합성 | 20 | 18 | 사용자 요구인 최신 AI 시스템 학습과 좋은 오픈소스 흡수에 직접 연결된다. |
| 구조 명확성 | 15 | 13 | README가 핵심 능력을 명확히 설명하지만 제품 표면이 넓다. |
| 검증 가능성 | 15 | 12 | clone과 문서 확인은 가능하지만 스켈레톤 적용은 별도 dry-run이 필요하다. |
| 유지보수 신호 | 15 | 14 | Nous Research 관리, 문서 사이트, 설치 경로, skills hub 신호가 있다. |
| 흡수 비용 | 15 | 12 | 개념 번역은 작지만 런타임 도입은 비용이 크다. |
| 보안/라이선스 리스크 | 10 | 8 | MIT이나 memory/user modeling은 별도 개인정보 경계가 필요하다. |
| 설명 가치 | 10 | 9 | 왜 오픈소스 우선 학습 루프가 필요한지 설명하기 좋다. |
| 합계 | 100 | 86 |  |

## Dry-Run 제안

- `proposal_needed`: yes
- `files_to_change`:
  - AGENTS.md
  - docs/PROJECT_PROFILE.template.md
  - docs/REFERENCE_DISCOVERY_WORKFLOW.md
- `behavior_change`: 에이전트가 새 프로젝트나 새 기능 구현 전에 관련 오픈소스와 기존 레퍼런스를 먼저 찾고 후보 카드로 평가하도록 한다.
- `validation_plan`: `python scripts/verify-skeleton.py`, `python scripts/validate-reference-candidates.py`, `python scripts/validate-reference-proposals.py`, `python scripts/list-open-questions.py --count`
- `rollback_or_stop_condition`: 문서가 Hermes 자체 도입처럼 읽히거나 개인 기억/글로벌 스킬 수정으로 해석되면 중단한다.
- `approval_required`: yes

## 최종 기록

- `final_status`: proposed
- `implemented_in`:
  - AGENTS.md
  - docs/PROJECT_PROFILE.template.md
- `validation_result`: candidate card created; validation pending
- `activity_log_entry`: runtime/activity-log.jsonl p0_open_source_first_contract_applied
- `notes`: Sources reviewed: local shallow clone at checked revision, README, LICENSE.
