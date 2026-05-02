# Everything Claude Code

## 기본 정보

- `name`: Everything Claude Code
- `url`: https://github.com/affaan-m/everything-claude-code
- `source_type`: repository
- `status`: proposed
- `searched_for`: agent harness performance system, research-first development, skills, hooks, memory, security scanning, Codex Claude compatibility
- `created_at`: 2026-04-29
- `reviewed_at`: 2026-04-29
- `reviewer`: Codex

## 왜 보는가

- `problem_statement`: 이 스켈레톤은 Codex/Claude 호환 운영 뼈대를 목표로 하지만, 오픈소스 우선 조사와 cross-harness 운영 품질을 기본 습관으로 강제하는 계약은 아직 충분히 강하지 않다.
- `why_it_matters`: Everything Claude Code는 skills, memory optimization, continuous learning, security scanning, research-first development, hooks, rules, MCP configs, Codex support를 통합한 agent harness performance system이다.
- `expected_value`: 이 저장소는 사용자가 말한 "나만 AI를 쓰는 것이 아니므로 이미 잘 만든 오픈소스를 활용해야 한다"는 운영 철학을 가장 직접적으로 뒷받침한다.

## 유용한 패턴

- `useful_patterns`:
  - skills를 primary workflow surface로 두고 commands는 compatibility surface로 다룬다.
  - research-first development와 quality gate를 에이전트 기본 습관으로 만든다.
  - hooks, memory, security scanning, MCP, rules를 한 시스템 안에서 관리한다.
  - Claude Code, Codex, Cursor, OpenCode, Gemini 등 여러 harness를 고려한다.
- `what_to_copy_conceptually`:
  - 새 구현 전에 reference research와 quality gate를 먼저 통과시키는 기준.
  - Codex/Claude 호환 진입 문서와 skills/rules 분리 모델.
  - 보안 스캔과 hook 중복/호환성 위험을 문서화하는 방식.
- `what_not_to_copy`:
  - 모든 plugin, hooks, commands, MCP 서버를 통째로 스켈레톤에 들여오지 않는다.
  - Claude Code plugin installer나 글로벌 사용자 설정을 공용 스켈레톤이 직접 관리하지 않는다.
  - 대규모 skill/command 목록을 새 프로젝트 기본값으로 복사하지 않는다.

## 증거

- `evidence_summary`: README는 ECC를 performance optimization system for AI agent harnesses로 설명하고, skills, memory optimization, continuous learning, security scanning, research-first development, hooks, rules, MCP configs, Codex support, cross-harness parity를 핵심 능력으로 제시한다.
- `local_clone_path`: runtime/external-repos/github.com/affaan-m__everything-claude-code
- `checked_revision`: c7c7d37f2946d7497577408d19adaee6a8341ddc
- `freshness_signal`: 2026-04-29에 GitHub 원본을 shallow clone했고 README와 LICENSE를 확인했다.
- `maintenance_signal`: README가 release notes, Codex support, Claude plugin, hooks, skills, security, FAQ, cross-harness sections를 폭넓게 유지한다.
- `documentation_signal`: README가 설치, 아키텍처, skills, hooks, security, Codex support, compatibility caveats를 매우 상세히 제공한다.
- `validation_signal`: clone revision과 MIT license를 확인했다. 이번 P0에서는 운영 계약과 후보 카드 기준선만 반영한다.
- `sources`:
  - {"path":"../AI_architecture_references/everything-claude-code/README.md","kind":"readme","evidence":"Agent catalog, command, and workflow examples were reviewed.","hash_or_line_ref":"local-reference"}
  - {"path":"../AI_architecture_references/everything-claude-code/.claude/commands","kind":"command_dir","evidence":"Reusable command pack structure was inspected conceptually.","hash_or_line_ref":"local-reference"}

## 리스크

- `license`: MIT license로 확인했다. 코드 복사는 가능성이 열려 있지만 P0에서는 개념만 참고한다.
- `security_or_privacy_risk`: hooks, MCP, memory, security scanning은 강력하지만 잘못 복사하면 사용자 설정이나 민감 경로에 영향을 줄 수 있다.
- `maintenance_risk`: Claude Code/Codex plugin 및 hook 동작은 도구 버전 변화에 민감하다.
- `complexity_risk`: 전체 시스템을 가져오면 공용 스켈레톤이 지나치게 크고 harness 종속적으로 변한다.
- `dependency_risk`: Node 기반 hooks, plugin, MCP 설정은 기본 Python/Markdown 스켈레톤의 경량 원칙과 충돌할 수 있다.
- `fit_risk`: 이 저장소는 성숙한 harness performance package이고, 현재 프로젝트는 프로젝트별 최소 운영 뼈대이므로 선택 흡수가 필요하다.

## 적용 후보

- `applies_to`: docs | rules | skills | scripts | tests
- `target_files_or_areas`:
  - AGENTS.md
  - docs/PROJECT_PROFILE.template.md
  - docs/REFERENCE_DISCOVERY_WORKFLOW.md
  - docs/WORKFLOW_CATALOG.md
  - scripts/
- `adoption_decision`: adapt
- `decision_reason`: research-first와 cross-harness 운영 품질은 현재 목적과 매우 잘 맞지만 대규모 plugin/skill/hook 전체 도입은 범위 밖이다.
- `next_action`: 오픈소스 우선 조사와 모듈형 흡수 판단을 P0 운영 계약으로 반영하고, 이후 P1에서 reference discovery workflow를 강화한다.

## 점수

| 기준 | 배점 | 점수 | 근거 |
| --- | ---: | ---: | --- |
| 문제 적합성 | 20 | 20 | Codex/Claude 호환 뼈대와 research-first 운영 철학에 직접 맞는다. |
| 구조 명확성 | 15 | 14 | README가 시스템 표면과 호환성 caveat를 상세히 설명한다. |
| 검증 가능성 | 15 | 14 | clone, 문서, license 확인이 가능하고 적용 단위도 문서/규칙으로 작게 나눌 수 있다. |
| 유지보수 신호 | 15 | 14 | release notes, Codex support, hooks caveats, FAQ가 활발히 관리된다. |
| 흡수 비용 | 15 | 13 | 개념 흡수는 작지만 전체 시스템 도입은 크다. |
| 보안/라이선스 리스크 | 10 | 8 | MIT이나 hooks/MCP/security 설정은 잘못 복사하면 위험하다. |
| 설명 가치 | 10 | 10 | 사용자의 "오픈소스를 잘 활용하라"는 핵심 교훈을 가장 잘 설명한다. |
| 합계 | 100 | 93 |  |

## Dry-Run 제안

- `proposal_needed`: yes
- `files_to_change`:
  - AGENTS.md
  - docs/PROJECT_PROFILE.template.md
  - docs/REFERENCE_DISCOVERY_WORKFLOW.md
- `behavior_change`: 에이전트가 구현 전에 research-first/open-source-first 단계를 거치고, 모듈형 흡수 후보와 직접 구현 예외를 명시하게 한다.
- `validation_plan`: `python scripts/verify-skeleton.py`, `python scripts/validate-reference-candidates.py`, `python scripts/validate-reference-proposals.py`, `python scripts/list-open-questions.py --count`
- `rollback_or_stop_condition`: 대규모 plugin, hooks, MCP, global settings를 승인 없이 복사하는 방향이 되면 중단한다.
- `approval_required`: yes

## 최종 기록

- `final_status`: proposed
- `implemented_in`:
  - AGENTS.md
  - docs/PROJECT_PROFILE.template.md
- `validation_result`: candidate card created; validation pending
- `activity_log_entry`: runtime/activity-log.jsonl p0_open_source_first_contract_applied
- `notes`: Sources reviewed: local shallow clone at checked revision, README, LICENSE.
