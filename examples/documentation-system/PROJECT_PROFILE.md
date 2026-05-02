# 프로젝트 프로필 예시: 문서화 시스템

## 한 문장 정의

코드베이스와 동기화되고 사람과 에이전트가 모두 찾기 쉬운 단일 출처 문서 시스템을 만드는 프로젝트 예시입니다.

## 기본 정보

- `project_name`: documentation-system-example
- `domain`: 기술 문서와 내부 지식 베이스
- `owner`: docs-team
- `status`: planning
- `created_at`: 2026-04-23

## 목표

- `primary_goal`: 코드베이스와 동기화되는 single-source documentation site를 만들고, 사람과 에이전트가 모두 검색 가능하게 한다.
- `target_users`: 엔지니어, 신규 입사자, 공개 subset을 사용하는 외부 파트너.
- `success_criteria`: 출시되는 모든 기능이 release 전 문서와 함께 반영되고, corpus 전체 검색/색인이 동작하며, stale page는 merge 전 lint에서 실패한다.
- `failure_definition`: 출시된 동작이 일주일 이상 문서에 반영되지 않거나, 내부 링크가 깨지거나, 파트너 공개 페이지에 잘못된 내용이 있다.
- `non_goals`: WYSIWYG authoring UI 구축, 장문의 product marketing content 대체.

## 프로젝트별 맥락

- `stack`: Markdown, static site generator, git
- `runtime_environment`: CI에서 빌드되어 내부/공개 host에 배포되는 static site
- `data_sources`: repo Markdown, code comments, changelog entries, ADRs
- `external_dependencies`: search indexer, hosting provider
- `security_or_privacy_constraints`: 내부 페이지가 public build에 노출되지 않아야 하며, partner docs는 confidential identifier를 제거한다.
- `compatibility_constraints`: 검색 색인된 public page의 기존 URL 구조를 유지한다.
- `project_specific_notes`: docs를 versioned artifact로 취급하고, behavior를 바꾸는 PR은 docs 변경 또는 `docs: n/a` 근거를 포함한다.

## 활성 운영 선택

- `active_workflows`: docs-review-per-pr, quarterly-docs-lint, plan-execute-validate-record
- `active_skills`: search-first, verification-loop, security-review
- `active_rules`: no-broken-links, single-source-of-truth, append-only-changelog
- `validation_summary`: link check, build success, staleness lint, non-author spot review를 release마다 실행한다.
- `pivot_summary`: 두 release cycle 연속 staleness나 search-discovery 불만이 반복되면 information architecture를 전환한다.

## 기능 추가/수정 판단 기준

새 문서 기능은 사용자가 찾기, 최신성 판단, 릴리즈 검증 중 하나를 더 잘할 수 있을 때 추가합니다. 단순 경로 목록 증가는 기능 개선으로 보지 않습니다.
