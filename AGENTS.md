# 에이전트 운영 가이드

Codex가 이 프로젝트에서 가장 먼저 읽는 문서입니다. 목적은 모든 세션이 같은 기준으로 프로젝트를 이해하고, 작업을 나누고, 결과를 검증하고, 다음 세션으로 이어지게 만드는 것입니다.

## 한 문장 정의

이 문서는 Codex가 프로젝트를 시작하거나 이어받을 때 반드시 확인해야 하는 목표, 운영 루프, 권한, 기록 규칙을 정리한 실행 진입점입니다.

## 무엇을 하는가

이 문서는 에이전트가 임의로 행동하지 않도록 작업 순서를 고정합니다. 먼저 프로젝트 목표와 성공 기준을 확인하고, 그다음 필요한 문서와 규칙만 읽고, 작업 범위를 정한 뒤 실행합니다. 실행 후에는 결과와 판단 근거를 기록합니다.

## 왜 필요한가

AI 에이전트는 긴 세션이나 복수 에이전트 작업에서 쉽게 “왜 이 일을 하는지”를 잊습니다. 이 문서는 프로젝트 프로필, 운영 루프, 권한, 로그, 인수인계 규칙을 같은 순서로 읽게 만들어 맥락 손실을 줄입니다.

## 먼저 읽을 것

작업을 시작할 때는 아래 순서로 읽습니다.

1. 프로젝트 프로필: 목표, 성공 기준, 제약 조건, 활성 워크플로를 확인합니다. 없거나 `primary_goal`/`success_criteria`/`failure_definition` 중 하나라도 비어 있으면 **대기하지 않고 먼저 질문**을 시작합니다. 사용자가 "시작하자" 같은 짧은 말만 해도 에이전트가 한 번에 한두 개씩 질문을 던져 프로필을 완성합니다. 상세 질문 순서는 `docs/PROJECT_PROFILE.template.md`의 Agent Fill-In Contract 참고.
2. 공통 규칙: 모든 프로젝트에 적용되는 기본 행동 기준을 확인합니다.
3. 운영 루프: 계획, 실행, 검증, 결정의 진행 조건을 확인합니다.
4. 세션 연속성 규칙: 이전 세션이 남긴 인수인계를 확인합니다.

필요할 때만 추가로 읽는 문서는 다음과 같습니다.

- 명세 문서: 구현 정답 조건이나 수용 테스트가 필요할 때.
- 아키텍처 문서: 시스템 전체 책임 구조가 필요할 때.
- 워크플로 카탈로그: 반복 가능한 업무를 고를 때.
- 에이전트 레지스트리: 반복 투입할 에이전트 상태와 권한을 확인할 때.
- 권한 문서: 읽기, 쓰기, 도구 사용 경계를 확인할 때.
- Notion 문서화 규칙: Notion에 문서를 작성하거나 수정할 때.
- 기능 결정 가이드: 기능을 추가, 수정, 보류, 삭제할지 판단할 때.

## 스킬 활성화

작업이 `skills/active/<skill>/SKILL.md`의 활성 조건과 맞으면 해당 SKILL.md를 먼저 읽고 실행합니다. 스킬이 없는 상황에서는 공통 규칙과 운영 루프만으로 진행합니다. `skills/`, `agents/`, `rules/`, `mcp/servers.yaml`, `references.yaml`이 canonical source입니다. `.codex/`, `.claude/`, `.mcp.json`은 `scripts/convert.py`가 만드는 산출물이며 직접 편집하지 않습니다.

## 어떻게 동작하는가

에이전트는 다음 흐름을 기본값으로 사용합니다.

```text
자연어 목표 수신
  -> agent-flow start --goal 로 mode와 next_command 확인
  -> 프로젝트 목표 확인
  -> 이전 세션 인수인계 확인
  -> 필요한 워크플로 선택
  -> 필요한 에이전트 역할 선택
  -> 권한과 쓰기 범위 확인
  -> 가장 작은 작업 단위 실행
  -> 검증
  -> 활동 로그 기록
  -> 필요한 경우 지식 업데이트 제안
  -> 세션 인수인계 갱신
```

## 결과는 무엇인가

이 문서를 따르는 세션은 다음 상태로 끝나야 합니다.

- 어떤 목표를 위해 작업했는지 설명할 수 있습니다.
- 어떤 파일이나 문서를 바꿨는지 추적할 수 있습니다.
- 검증을 실행했거나 실행하지 못한 이유를 설명할 수 있습니다.
- 다음 세션이 이어받을 수 있는 인수인계가 갱신됩니다.
- 반복 에이전트 작업은 실행 기록과 목표 계보를 남깁니다.

## 운영 규칙

- `config/roles.yaml`이 역할별 primary와 모델의 단일 진실 소스입니다. 문서와 스크립트는 특정 모델명보다 planner, implementer, researcher, verifier, evaluator 역할 이름을 우선 사용합니다.
- 사용자가 자연어로 목표를 말하면 에이전트는 먼저 `python3 scripts/agent-flow.py start --goal "<goal>" --format json`을 실행해 `mode`, `reason`, `next_command`, `confidence`, `requires_confirmation`, `write_policy`를 확인합니다. 사용자는 목표, 제약, 승인, 거절을 채팅으로 제공하고, 에이전트가 public 진입점인 `scripts/agent-flow.py`를 통해 내부 스크립트를 호출합니다.
- 에이전트가 기본으로 직접 호출하는 public command는 `scripts/agent-flow.py` 하나입니다. 다른 `scripts/*.py`는 `scripts/catalog.yaml`의 internal tool로 보고, 디버깅이나 특정 단계 재실행이 아니면 `agent-flow`를 통해 호출합니다.
- `write_policy=read_only`인 흐름은 조사와 보고까지만 수행합니다. `manual_work_required`는 사용자의 구현 범위가 확정된 뒤 파일 수정을 시작하고, `write_with_confirmation`은 검증/closeout처럼 승인된 append-only 기록 또는 종료 단계에서만 사용합니다.
- `mode=build`는 바로 구현하지 않습니다. `build_intake`의 질문으로 범위와 수용 기준을 정리하고, 승인된 뒤 `plans/active/<seq>-<slug>.md`를 만든 다음 구현합니다.
- `mode=research` 또는 `reference_review_required`에서는 `next_command`에 포함된 `--goal`을 유지해 사용자가 말한 ECC, opencode, hermes 같은 named reference가 다음 후보 선택까지 전달되게 합니다.
- 단일 세션은 30분 또는 컨텍스트 50% 중 먼저 도달하는 지점에서 멈춥니다. 마일스톤에 도달하면 `state/progress.md`와 세션 인수인계를 갱신하고, 사용자가 continue라고 말하기 전에는 다음 큰 단계로 넘어가지 않습니다.
- 사용자 컨펌 필수 액션은 `config/policy.yaml`의 `confirmation_required`를 따릅니다. git push, 파일/디렉터리 삭제, 의존성 변경, 비용 발생 가능 외부 API 호출, MCP 서버 추가/제거, skill 승격/강등은 실행 전 확인합니다.
- plan은 `plans/active/<seq>-<slug>.md`에서 시작하고 완료 시 `plans/done/`, 3회 초과 재계획 실패 시 `plans/failed/`로 이동합니다. 재계획 기록은 덮어쓰지 않고 누적합니다.
- 프로젝트별 사실은 프로젝트 프로필에 둡니다.
- 재사용 가능한 방법론은 공통 규칙이나 스킬로 옮깁니다.
- 불확실하거나 자동 생성된 변경은 제안 영역에 먼저 둡니다.
- 새 프로젝트, 새 시스템, 익숙하지 않은 도메인, 기능 구현 요청이 들어오면 바로 직접 구현하지 않고 먼저 관련 오픈소스, 공식 문서, 기존 참고 시스템을 찾습니다. 사용자가 제공한 레퍼런스가 있으면 우선 검토하고, 공개 저장소는 후보 카드와 라이선스/유지보수/검증 근거를 남긴 뒤 dependency, wrapper, partial copy, concept-only 중 맞는 방식으로 모듈형 흡수합니다.
- 개인 로컬 사용처럼 외부 배포가 없는 작업에서는 라이선스가 자동 차단 사유가 아닙니다. 이 경우에도 출처, 라이선스, 확인한 revision, 복사 범위, 재배포 금지 또는 재검토 조건을 후보 카드와 dry-run 제안에 남기면 일부 코드 복사(`partial_copy`)를 승인 가능한 선택지로 둡니다.
- 명백히 참고할 오픈소스가 있는 영역에서 처음부터 직접 구현하려면, 후보 카드 없이 진행하는 이유와 검증 방법을 활동 로그나 세션 인수인계에 남깁니다. 외부 코드나 구조를 장기 규칙, 스킬, 스크립트, 모듈 구조로 옮기려면 `docs/REFERENCE_DISCOVERY_WORKFLOW.md`의 후보 카드 -> dry-run 제안 -> 승인 -> 반영 순서를 따릅니다.
- 주요 실행과 결정은 활동 로그에 남깁니다. 에이전트가 직접 `scripts/hooks/post-tool-use-log.py`를 호출하거나, 한 줄을 `runtime/activity-log.jsonl`에 append합니다. 스키마는 `docs/RUNTIME_EVENT_SCHEMA.md`. 세션 인수인계를 저장할 때는 `{"phase":"session","action":"handoff_saved",...}` 이벤트도 함께 남깁니다(상세: `docs/SESSION_CONTINUITY.md`).
- 반복 에이전트 실행은 에이전트 실행 로그에 남깁니다.
- 위임되거나 반복되는 에이전트 작업은 목표 계보(goal lineage: 상위 목표 → 하위 목표로 이어지는 호출 체인)를 포함합니다.
- 장기 지식 문서는 에이전트가 직접 수정하지 않고 제안으로 남깁니다.
- 런타임이 소유한 Codex 설정은 수정하지 않습니다.
- 세션 종료, 큰 작업 완료, 컨텍스트 한계가 오기 전에는 인수인계를 갱신합니다.
- 사용자가 프로젝트 건강 확인을 요청하거나 구조 변경 후에는 `python3 scripts/verify-skeleton.py`를 실행합니다. 종료 코드 0이면 모든 검사를 통과했다는 의미입니다.
- Notion을 사용하는 프로젝트에서만 Notion 규칙을 적용합니다. 사용 시에는 데이터베이스 페이지로만 만들고, 페이지 안에 자식 페이지를 만들지 않습니다. **새 페이지를 만들기 전에 DB를 검색해 유사 페이지가 있는지 확인**하고, 있으면 업데이트·대체·공존 중 사용자에게 확인합니다. 대체 시 `Superseded By`·`Superseded At`·`Status=superseded`를 같은 작업에서 설정합니다. 상세: `docs/NOTION_DOCUMENTATION_RULES.md` "중복 방지 프로토콜".
- Notion 문서는 기능 기준으로 작성합니다. 단순 구현 기록, 파일 목록, 짧은 요약만 있는 페이지는 완료로 보지 않습니다. 페이지 본문에는 기능이 해결하는 사용자 문제, 동작 흐름, 입력과 출력, 성공 상태, 실패 신호, 추가/수정/보류 판단 기준이 있어야 합니다. 초안 Markdown을 만들 수 있으면 `python3 scripts/notion-doc-quality-check.py <draft.md>`로 검사한 뒤 작성합니다.
- Notion 기능 문서는 처음 보는 사람이 그 문서만 읽고도 기능의 역할, 만든 이유, 실제 동작, 사용 시점, 결과물, 고장 신호를 이해할 수 있어야 합니다. 기존 운영 규칙 문서처럼 `한 문장 정의 -> 무엇을 하는가 -> 왜 필요한가 -> 어떻게 동작하는가 -> 결과 -> 판단 기준 -> 구현 연결 정보` 흐름을 기본 골격으로 씁니다.
- 기능 요청이 들어오면 먼저 `docs/FEATURE_DECISION_GUIDE.md`의 추가/수정/보류/삭제 판단 기준을 따릅니다. 각 도메인 문서의 "기능 추가/수정 판단 기준" 섹션은 이 canonical 기준에 종속됩니다.
- MCP 서버와 도구 수를 절제합니다(프로젝트당 서버 ≤ 10, 도구 총합 ≤ 80). 초과 필요시 `docs/PROJECT_OPERATING_PLAN.md`에 사유 기록. 상세: `rules/common/mcp-discipline.md`.
- 새 코드와 파일을 쓸 때 공통 스타일(`rules/common/code-style.md`), 권고 레이아웃(`rules/common/directory-layout.md`), 임시 파일 규칙(`rules/common/ephemeral-files.md`)을 따릅니다. 특히 `tmp-`/`scratch-` 접두사 또는 `-smoke-` 패턴의 임시 파일·디렉터리는 세션 종료 전에 삭제하고 커밋하지 않습니다.

## Skill 영속화 정책

- v1에서는 자동 promotion/demotion을 실행하지 않고 사용자에게 제안만 합니다.
- 한 프로젝트 안에서 20회 이상 사용되고 성공률 85% 이상이면 candidate skill의 active 승격을 제안합니다.
- active skill 성공률이 70% 미만으로 떨어지면 deprecated 강등을 제안합니다.
- 성공은 verify 게이트 통과와 사용자 reject 없음으로 계산합니다.
- 새 skill 또는 skill 변경은 `scripts/eval.py <skill-name>`로 골든 케이스를 확인합니다. 골든 케이스가 없으면 실패가 아니라 `regression_uncovered` 상태로 기록합니다.

## Verify 게이트

모든 영속 변경은 가능한 범위에서 `scripts/verify.py` 또는 단계별 등가 검증을 통과해야 합니다.

```text
check -> lint -> unit -> smoke -> integration
```

기본 연결은 다음과 같습니다.

- check: `scripts/verify-skeleton.py`
- lint: `scripts/skill-surface-check.py`
- unit: `python -m unittest discover -s tests -v`
- smoke: 새 프로젝트 부트스트랩 후 verify
- integration: `scripts/verify-parity.py`

## Command Surface

| 표면 | 사용 조건 | 예 |
| --- | --- | --- |
| 기본 public command | 모든 자연어 요청의 시작점 | `python3 scripts/agent-flow.py start --goal "<goal>" --format json` |
| bootstrap 예외 | 새 프로젝트 폴더를 처음 시드할 때만 | `python3 scripts/bootstrap/new-project.py --name <name> --target <path>` |
| debug/validation 예외 | 특정 실패를 좁히거나 검증 단계를 재실행할 때만 | `python3 scripts/verify.py`, `python3 scripts/quality-gate.py --format json` |
| internal tool 직접 호출 | agent-flow 출력, catalog, 테스트가 특정 스크립트를 요구할 때만 | `python3 scripts/reference-task-queue.py check` |

## 매 세션 종료 체크리스트

- [ ] `state/progress.md` 갱신
- [ ] 새 결정이 있으면 `state/decisions.md`에 append
- [ ] 새 블로커가 있으면 `state/blockers.md`에 기록
- [ ] 실패한 접근이 있으면 `state/failures.jsonl`에 1줄 추가
- [ ] 비용/토큰 정보를 알 수 있으면 `state/cost-log.jsonl`에 기록
- [ ] 세션 인수인계 `runtime/state/session-handoff.md` 갱신
- [ ] 활성 plan의 status 갱신

## 새 프로젝트를 만들 때

사용자가 직접 채워야 하는 최소 문서는 프로젝트 프로필 하나입니다. 나머지는 실제 필요가 생겼을 때 대화로 만듭니다.

1. 프로필이 없거나 비어 있으면 템플릿을 기준으로 질문합니다.
2. 사용자가 말하지 않은 사실은 만들지 않습니다.
3. 참고해야 할 오픈소스, 경쟁 제품, 공식 문서, 기존 레퍼런스가 있는지 확인합니다. 있으면 `research/reference-candidates/`에 후보 카드로 남기고, 저장소 구조 분석이 필요하면 `runtime/external-repos/` 아래에 clone합니다.
4. 구현 정답 조건이 필요할 때만 명세 문서를 만듭니다.
5. 상세 검증이나 권한이 필요할 때만 운영 계획을 만듭니다.
6. 반복되는 업무가 확인될 때만 워크플로, 에이전트, 스킬을 추가합니다.
7. 자동화는 승인 전까지 dry-run 또는 제안 형태로 둡니다.

## 기능 추가/수정 판단 기준

에이전트는 기능 요청을 받으면 먼저 기존 기능으로 해결 가능한지 확인합니다. 사용자가 결정을 내릴 수 없을 만큼 설명이 부족한 경우에는 새 기능보다 문서와 흐름의 수정을 우선합니다. 새 기능은 독립 목표, 입력, 출력, 검증 기준이 분명할 때만 추가합니다.

## 구현 연결 정보

이 섹션은 파일을 찾아야 하는 에이전트를 위한 보조 정보입니다.

- 프로젝트 프로필 템플릿: `docs/PROJECT_PROFILE.template.md`
- 공통 규칙: `rules/common/README.md`
- 운영 루프: `docs/OPERATING_LOOP.md`
- 세션 연속성: `docs/SESSION_CONTINUITY.md`
- 권한 문서: `codex/rules/AGENT_PERMISSIONS.md`
- 에이전트 레지스트리: `docs/AGENT_REGISTRY.md`
- 워크플로 카탈로그: `docs/WORKFLOW_CATALOG.md`
- 기능 결정 기준: `docs/FEATURE_DECISION_GUIDE.md`
- 문서화 스타일 기준: `docs/DOCUMENTATION_STYLE_GUIDE.md`
- Notion 문서화 규칙: `docs/NOTION_DOCUMENTATION_RULES.md`
- 스켈레톤 건강 체크: `scripts/verify-skeleton.py`

## 에이전트 책임: copied-source ledger

오픈소스 코드를 실제 로컬 파일로 복사하는 경우, 사용자가 별도로 장부를 남기지 않습니다. 에이전트가 복사 작업과 같은 변경 단위 안에서 다음을 모두 수행해야 합니다.

- 후보 카드에 `adoption_decision: copy`와 `what_to_copy_directly`, `copy_boundary`를 기록합니다.
- reference-adoption 제안서에 `absorption_mode: partial_copy`와 `copy_boundary`를 기록합니다.
- 실제 파일을 수정한 직후 `python3 scripts/reference-copy-ledger.py add ...`로 `runtime/reference-copy-ledger.jsonl`에 출처, 라이선스, revision, 원본 경로, 로컬 경로, 복사 범위를 append합니다.
- `python3 scripts/reference-copy-ledger.py check`와 `python3 scripts/security-scan.py --strict`로 기록 누락이 없는지 검증합니다.
- 활동 로그와 세션 인수인계에 어떤 외부 코드가 어떤 로컬 경로로 복사됐는지 요약합니다.

사용자는 채팅에서 승인하거나 방향을 정할 뿐, 후보 카드·제안서·장부·검증 로그를 직접 편집하거나 실행하지 않습니다.
