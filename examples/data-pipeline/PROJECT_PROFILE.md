# 프로젝트 프로필 예시: 데이터 파이프라인

## 한 문장 정의

원천 이벤트를 매일 분석 가능한 데이터셋으로 변환하고 품질 검증까지 재현 가능하게 관리하는 프로젝트 예시입니다.

## 기본 정보

- `project_name`: data-pipeline-example
- `domain`: 데이터 엔지니어링
- `owner`: data-platform-team
- `status`: planning
- `created_at`: 2026-04-23

## 목표

- `primary_goal`: 원천 이벤트를 매일 분석 가능한 데이터셋으로 변환하는 batch pipeline을 만들고, 재현 가능한 품질 검사를 포함한다.
- `target_users`: 분석가, BI dashboard, downstream ML feature job.
- `success_criteria`: 일일 실행이 정해진 시간에 성공하고, 출력 데이터가 schema와 품질 검사를 통과하며, 실패가 한 on-call cycle 안에 조치 가능하다.
- `failure_definition`: 일일 partition 누락, silent schema drift, 기준치를 넘는 중복 record.
- `non_goals`: v1에서 real-time streaming ingestion 구축.

## 프로젝트별 맥락

- `stack`: Python, SQL, dbt, object storage, warehouse
- `runtime_environment`: CI/CD scheduler에서 실행되는 containerized batch job
- `data_sources`: app event logs, billing exports
- `external_dependencies`: warehouse account, object storage bucket
- `security_or_privacy_constraints`: raw PII를 로그에 남기지 않고 service account 권한을 최소화한다.
- `compatibility_constraints`: migration window 전까지 v1 downstream table contract를 유지한다.
- `project_specific_notes`: idempotent write와 immutable raw zone을 사용한다.

## 활성 운영 선택

- `active_workflows`: data-contract-review, plan-execute-validate-record
- `active_skills`: search-first, tdd-workflow, verification-loop, security-review
- `active_rules`: append-only logging, smallest-verifiable-change
- `validation_summary`: partition별 schema, uniqueness, null-rate check를 실행한다.
- `pivot_summary`: 두 번 연속 root-cause isolation에 실패하면 설계를 전환한다.

## 기능 추가/수정 판단 기준

새 파이프라인 단계는 입력 계약, 출력 계약, 품질 기준, 재처리 방식이 명확할 때만 추가합니다. 기존 단계의 설명이나 검증이 부족한 경우에는 새 단계보다 contract와 validation을 먼저 수정합니다.
