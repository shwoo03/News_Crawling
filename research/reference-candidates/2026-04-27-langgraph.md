# LangGraph

이 후보 카드는 외부 사례 도입 프로세스를 검증하기 위한 예시 후보입니다. LangGraph를 이 스켈레톤에 설치하거나 기본 의존성으로 도입하려는 계획이 아닙니다.

## 기본 정보

- `name`: LangGraph
- `url`: https://github.com/langchain-ai/langgraph
- `source_type`: repository
- `status`: proposed
- `searched_for`: long-running stateful agent workflow, durable execution, human-in-the-loop, checkpointing
- `created_at`: 2026-04-27
- `reviewed_at`: 2026-04-27
- `reviewer`: Codex

## 왜 보는가

- `problem_statement`: 이 스켈레톤은 세션 인수인계와 활동 로그를 사용하지만, 장기 에이전트 작업을 "재개 가능한 실행 단위"로 모델링하는 기준은 아직 가볍다. 이 카드는 그 개선 가능성을 검토하는 예시 후보다.
- `why_it_matters`: LangGraph는 장기 실행, 상태 유지, human-in-the-loop, durable execution을 명시적 제품/문서 개념으로 다루므로 운영 루프와 세션 연속성 개선에 참고 가치가 있다.
- `expected_value`: 프레임워크를 도입하지 않고도 checkpoint, thread/session id, idempotent side effect, resume-safe task 개념을 스켈레톤 운영 규칙으로 번역할 수 있다.

## 유용한 패턴

- `useful_patterns`:
  - long-running agent workflow를 stateful graph로 모델링한다.
  - durable execution을 위해 checkpoint와 thread identifier를 요구한다.
  - 재개 시 부작용이 반복되지 않도록 side effect를 task/node로 감싼다.
  - human-in-the-loop를 실행 중단과 재개가 가능한 정상 흐름으로 다룬다.
- `what_to_copy_conceptually`:
  - 세션 인수인계를 단순 요약이 아니라 resume-safe checkpoint로 취급하는 관점.
  - 파일 쓰기, API 호출, 로그 append 같은 side effect를 idempotent task로 분리해야 한다는 규칙.
  - 장기 작업에는 실행 식별자와 재개 지점을 남겨야 한다는 요구.
- `what_not_to_copy`:
  - LangGraph 런타임이나 그래프 API를 이 스켈레톤의 기본 의존성으로 추가하지 않는다.
  - 모든 운영 절차를 노드/엣지 코드 구조로 바꾸지 않는다.
  - LangSmith나 LangChain 생태계 의존을 기본값으로 두지 않는다.

## 증거

- `evidence_summary`: GitHub 저장소는 LangGraph를 "long-running, stateful agents"용 low-level orchestration framework로 설명하고, durable execution, human-in-the-loop, memory, observability, production deployment를 핵심 가치로 제시한다. 공식 문서는 durable execution에 checkpointer, thread identifier, side-effect wrapping, idempotency가 필요하다고 설명한다.
- `local_clone_path`: not cloned
- `checked_revision`: not checked; GitHub repository page and official docs reviewed
- `freshness_signal`: GitHub 페이지 기준 최신 릴리스가 2026-04-24에 표시되어 있고, 공식 문서는 2026-04-27 현재 최근 크롤링 결과가 있다.
- `maintenance_signal`: GitHub 페이지 기준 약 30.5k stars, 5.2k forks, 505 releases, MIT license가 표시된다.
- `documentation_signal`: 공식 Python/JavaScript 문서가 durable execution, persistence, human-in-the-loop 등 핵심 개념을 별도 페이지로 설명한다.
- `validation_signal`: 운영 개념은 공식 문서로 확인 가능하지만, 이 스켈레톤에 바로 도입할 코드나 의존성은 없다. 적용 전 dry-run 설계가 필요하다.
- `sources`:
  - {"path":"https://github.com/langchain-ai/langgraph","kind":"repository","evidence":"Durable execution and checkpointing concept source for the dry-run example.","hash_or_line_ref":"external-reference"}

## 리스크

- `license`: MIT license로 표시된다. 개념 참고는 낮은 리스크지만 코드 복사는 별도 라이선스 검토가 필요하다.
- `security_or_privacy_risk`: 외부 런타임을 도입하면 상태 저장소와 trace 데이터에 민감 정보가 남을 수 있다. 현재 후보는 개념만 참고한다.
- `maintenance_risk`: 활발한 프로젝트라 문서와 API가 빠르게 바뀔 수 있다. 공식 문서 기준으로 재확인해야 한다.
- `complexity_risk`: LangGraph 전체 구조는 이 스켈레톤보다 훨씬 무겁다. 통째로 가져오면 운영 문서가 프레임워크 종속으로 변할 수 있다.
- `dependency_risk`: 기본 스켈레톤은 외부 패키지 없는 Python 스크립트를 선호하므로 런타임 의존성 추가는 부적합하다.
- `fit_risk`: 그래프 실행 모델은 구현 프레임워크에는 적합하지만, 현재 목표는 에이전트 운영 스켈레톤이다. 개념만 번역해야 한다.

## 적용 후보

- `applies_to`: docs | rules | runtime
- `target_files_or_areas`:
  - `docs/SESSION_CONTINUITY.md`
  - `docs/OPERATING_LOOP.md`
  - `docs/RUNTIME_EVENT_SCHEMA.md`
  - `rules/common/verification-loop.md`
- `adoption_decision`: adapt
- `decision_reason`: 프레임워크 도입은 과하지만 durable execution과 idempotent side effect 원칙은 현재 세션 연속성 규칙을 강화하는 데 직접적으로 유용하다.
- `next_action`: 외부 후보 기반 resume-safe checkpoint dry-run 제안 예시를 만든다.

## 점수

| 기준 | 배점 | 점수 | 근거 |
| --- | ---: | ---: | --- |
| 문제 적합성 | 20 | 18 | 장기 에이전트 실행과 재개 가능성이라는 현재 운영 문제에 직접 연결된다. |
| 구조 명확성 | 15 | 14 | durable execution, thread id, checkpoint, task wrapping 경계가 명확하다. |
| 검증 가능성 | 15 | 13 | 공식 문서와 저장소 근거는 충분하지만 스켈레톤 적용 검증은 별도 dry-run이 필요하다. |
| 유지보수 신호 | 15 | 15 | GitHub 페이지 기준 stars, forks, releases, 최근 릴리스 신호가 강하다. |
| 흡수 비용 | 15 | 12 | 개념만 문서 규칙으로 번역하면 작지만, 코드 도입은 비용이 크다. |
| 보안/라이선스 리스크 | 10 | 8 | MIT license이나 상태 저장/trace 데이터 리스크는 적용 시 별도 검토가 필요하다. |
| 설명 가치 | 10 | 9 | 세션 연속성과 부작용 재실행 문제를 사용자에게 설명하기 좋다. |
| 합계 | 100 | 89 |  |

## Dry-Run 제안

- `proposal_needed`: yes
- `files_to_change`:
  - `docs/SESSION_CONTINUITY.md`
  - `docs/OPERATING_LOOP.md`
  - `docs/RUNTIME_EVENT_SCHEMA.md`
- `behavior_change`: 장기 작업 인수인계 시 재개 식별자, 마지막 안전 checkpoint, 재실행하면 안 되는 side effect, idempotency 확인을 남기도록 한다.
- `validation_plan`: `python scripts/verify-skeleton.py`, `python scripts/validate-reference-candidates.py`, `python scripts/list-open-questions.py --count`
- `rollback_or_stop_condition`: 운영 문서가 특정 프레임워크 의존처럼 읽히거나, 후보 카드 없이 장기 규칙을 직접 수정하려 하면 중단한다.
- `approval_required`: yes

## 최종 기록

- `final_status`: proposed
- `implemented_in`:
  - `runtime/proposals/reference-adoption/2026-04-27-example-resume-safe-checkpoint.md`
- `validation_result`: dry-run proposal created; pending user approval for actual documentation changes
- `activity_log_entry`: pending final log append
- `notes`: Sources reviewed: GitHub repository page `https://github.com/langchain-ai/langgraph`, Python durable execution docs `https://docs.langchain.com/oss/python/langgraph/durable-execution`, Python overview `https://docs.langchain.com/oss/python/langgraph/overview`.
