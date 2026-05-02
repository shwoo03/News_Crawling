# 프로젝트 프로필 예시: 웹 애플리케이션

## 한 문장 정의

명확한 사용자 흐름, 측정 가능한 품질 기준, 배포 가능한 릴리즈 흐름을 갖춘 풀스택 웹 애플리케이션 프로젝트 예시입니다.

## 기본 정보

- `project_name`: web-app-example
- `domain`: 풀스택 웹 애플리케이션
- `owner`: product-engineering
- `status`: planning
- `created_at`: 2026-04-23

## 목표

- `primary_goal`: 명확한 core user flow와 측정 가능한 품질 기준을 가진 신뢰성 있는 웹 애플리케이션을 만들고, main branch merge마다 배포 가능하게 한다.
- `target_users`: 핵심 task flow를 완료하는 최종 사용자와 시스템을 구성/모니터링하는 내부 운영자.
- `success_criteria`: core flow가 정의된 latency/error budget 안에서 완료되고, staging smoke test가 production deploy 전 통과하며, 사용자에게 보이는 모든 변경에 acceptance test가 있다.
- `failure_definition`: production에서 core flow가 깨지거나, silent regression이 배포되거나, evidence trail 없이 release rollback이 발생한다.
- `non_goals`: v1에서 multi-region active-active deployment 또는 native mobile client 구축.

## 프로젝트별 맥락

- `stack`: TypeScript, React, Node.js API, PostgreSQL, containerized deploy
- `runtime_environment`: CI/CD와 staging environment가 있는 managed cloud platform
- `data_sources`: user interactions, first-party analytics, billing events
- `external_dependencies`: auth provider, email/SMS, payment processor
- `security_or_privacy_constraints`: 로그의 PII를 최소화하고, secret은 managed vault로만 관리하며, tenant별 data isolation을 유지한다.
- `compatibility_constraints`: 기존 API client를 위한 public API contract와 release별 browser support matrix를 유지한다.
- `project_specific_notes`: 사용자에게 보이는 변경은 feature flag로 보호하고 backward-compatible migration을 선호한다.

## 활성 운영 선택

- `active_workflows`: feature-flag-rollout, plan-execute-validate-record, weekly-incident-review
- `active_skills`: search-first, tdd-workflow, verification-loop, security-review
- `active_rules`: smallest-verifiable-change, no-secret-in-client, feature-flag-every-ui-change
- `validation_summary`: unit, integration, staging E2E smoke, error-budget dashboard check를 release 전 실행한다.
- `pivot_summary`: error-budget regression이 두 release 연속 지속되거나 deploy frequency가 target 아래로 떨어지면 architecture를 전환한다.

## 기능 추가/수정 판단 기준

새 기능은 core user flow, 운영 안정성, 배포 신뢰도 중 하나를 개선해야 합니다. 품질 예산과 acceptance test가 없으면 기능 추가보다 검증 기준을 먼저 정의합니다.
