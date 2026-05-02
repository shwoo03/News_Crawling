# 프로젝트 프로필 예시: 학습 시스템

## 한 문장 정의

학습자의 lesson, quiz, recommendation 흐름을 추적하고 mastery progression을 설명 가능하게 관리하는 프로젝트 예시입니다.

## 기본 정보

- `project_name`: learning-system-example
- `domain`: 교육 기술
- `owner`: learning-platform-team
- `status`: planning
- `created_at`: 2026-04-23

## 목표

- `primary_goal`: 학습자별 다음 lesson을 추천하고 mastery progression을 추적하는 adaptive learning loop를 제공한다.
- `target_users`: 학습자, 강사, 학습 운영 담당자.
- `success_criteria`: 학습자가 lesson -> quiz -> recommendation cycle을 완료할 수 있고, mastery state 변경 이유가 설명 가능하며, 핵심 흐름이 자동 검증된다.
- `failure_definition`: recommendation loop가 깨지거나, mastery state가 불일치하거나, 강사가 progression을 감사할 수 없다.
- `non_goals`: v1에서 enterprise LMS integration 구축.

## 프로젝트별 맥락

- `stack`: TypeScript, Next.js, Python API, PostgreSQL
- `runtime_environment`: cloud-hosted web app and API services
- `data_sources`: lesson content, quiz attempts, learner profiles
- `external_dependencies`: auth provider, email service
- `security_or_privacy_constraints`: learner PII를 보호하고 quiz telemetry 보관을 최소화하며 role-based access를 강제한다.
- `compatibility_constraints`: 기존 mobile client의 API contract를 유지한다.
- `project_specific_notes`: recommendation rule은 각 추천의 human-readable rationale을 제공해야 한다.

## 활성 운영 선택

- `active_workflows`: hypothesis-driven-feature-loop, plan-execute-validate-record
- `active_skills`: search-first, tdd-workflow, verification-loop, security-review
- `active_rules`: small-increments, test-before-claim, no-secret-in-client
- `validation_summary`: completion rate, quiz accuracy trend, sparse history fallback behavior를 추적한다.
- `pivot_summary`: 두 반복 후에도 목표 completion lift를 달성하지 못하면 recommendation strategy를 전환한다.

## 기능 추가/수정 판단 기준

새 학습 기능은 학습자 행동, 강사 감사 가능성, mastery 설명 가능성 중 하나를 개선해야 합니다. 모델 복잡도만 늘고 검증 가능한 학습 성과가 없으면 보류합니다.
