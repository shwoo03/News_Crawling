# 프로젝트 운영 계획 템플릿

프로젝트 프로필보다 자세한 운영 설정이 필요할 때만 이 파일을 `docs/PROJECT_OPERATING_PLAN.md`로 복사합니다.

## 한 문장 정의

프로젝트 운영 계획은 공용 운영 시스템을 특정 프로젝트의 에이전트, 검증, 피벗, 지식 정책에 맞게 구체화하는 문서입니다.

## 무엇을 하는가

이 문서는 프로젝트마다 달라질 수 있는 운영 기준을 묶습니다. 반복 에이전트, 검증 방법, 효과 점수, 피벗 임계값, 지식 정책이 공통 기본값으로 부족할 때 사용합니다.

## 왜 필요한가

모든 프로젝트가 같은 검증 횟수, 같은 예산, 같은 피벗 기준을 쓰지는 않습니다. 다만 이런 기준을 대화 속에만 두면 다음 세션이 잊습니다. 운영 계획은 프로젝트별 운영 결정을 명시적으로 남기기 위해 필요합니다.

## 에이전트 운영

- `registered_agents`:
- `workflow_catalog_entries`:
- `agent_permissions`:
- `scheduled_workflows`:
- `agent_run_log`: runtime/agent-runs.jsonl

## 평가 방법

- `evaluation_method`:
- `micro_validation`:
- `medium_validation`:
- `full_validation`:
- `trial_count`:
- `outcome_classification`:

허용 결과 분류:

- `genuine_success`
- `partial_progress`
- `timeout`
- `infra_error`
- `blocked_by_policy`

## 효과 점수

단계별 효과를 0부터 10까지 점수로 정의합니다.

- `score_formula`:
- `baseline`:
- `lock_threshold`:
- `regression_threshold`:
- `replacement_threshold`:

## 피벗 임계값

- `per_step_triggers`:
- `per_project_triggers`:
- `escalation_ladder`:
- `salvage_required`: true

## 지식 정책

- `append_only_logs`: true
- `append_only_agent_runs`: true
- `auto_apply`: false
- `proposal_review_owner`:
- `knowledge_editor`: human only

## 운영 체크리스트

- [ ] 반복 에이전트가 등록되어 있습니다.
- [ ] 에이전트 권한이 명시되어 있습니다.
- [ ] 검증 방법이 정의되어 있습니다.
- [ ] 피벗 임계값이 정의되어 있습니다.
- [ ] 활동 로그 기록이 시작됐습니다.

## 결과는 무엇인가

운영 계획이 있으면 프로젝트별 실행 기준이 대화가 아니라 문서로 남습니다. 에이전트는 어떤 검증을 몇 번 해야 하는지, 어떤 실패에서 피벗해야 하는지, 어떤 변경이 승인 대상인지 알 수 있습니다.

## 기능 추가/수정 판단 기준

공통 운영 기준으로 충분하면 이 문서를 만들지 않습니다. 프로젝트가 별도 에이전트 예산, 검증 횟수, 피벗 임계값, 지식 승인자를 필요로 할 때만 만듭니다. 운영 계획이 프로젝트 목표 설명으로 커지고 있다면 그 내용은 프로젝트 프로필로 옮깁니다.
