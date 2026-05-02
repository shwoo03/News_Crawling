# 프로젝트 프로필: News_Crawling

<!-- AI_architecture harness가 2026-05-02에 기존 프로젝트에 적용되며 갱신했습니다. 모르는 값은 `[NEEDS CLARIFICATION: <질문>]` 또는 `TBD`로 둡니다. -->

## 기본 정보

- `project_name`: News_Crawling
- `domain`: cli
- `owner`: shwoo
- `status`: active
- `created_at`: 2026-05-02

## 목표

- `primary_goal`: OpenAI 뉴스 RSS를 감지하고 새 글 본문을 Groq API로 요약한 뒤 Discord Webhook으로 전송하는 Node.js/TypeScript 워커를 안정적으로 운영한다.
- `target_users`: OpenAI 관련 새 글을 빠르게 받고 싶은 개인 운영자 또는 소규모 팀.
- `success_criteria`: `npm test`가 통과하고, `npm run top` 테스트 모드가 설정된 환경 변수에서 상위 뉴스 요약을 생성/전송할 수 있으며, 워커 모드는 SQLite 중복 방지를 통해 같은 URL을 반복 전송하지 않는다.
- `failure_definition`: 필수 환경 변수 누락을 조용히 무시하거나, 같은 기사 URL을 반복 전송하거나, 요약/전송 실패가 로그 없이 묻히거나, `.env` 같은 secret 파일을 새로 커밋 대상으로 남기는 상태.
- `non_goals`: 범용 뉴스 플랫폼, 다중 사용자 SaaS, 실시간 웹 UI, 무제한 소스 크롤링.

## 프로젝트별 맥락

- `stack`: Node.js, TypeScript, Playwright, SQLite, Docker Compose
- `runtime_environment`: 로컬 Node 실행 또는 Docker Compose 워커. 실행 명령은 `npm start`, 테스트/단발 실행은 `npm run top`, 회귀 테스트는 `npm test`.
- `data_sources`: OpenAI RSS feed와 OpenAI 기사 상세 페이지.
- `external_dependencies`: Groq API, Discord Webhook, Playwright browser runtime, SQLite 파일 저장소.
- `security_or_privacy_constraints`: `GROQ_API_KEY`, `DISCORD_WEBHOOK_URL`, `DISCORD_WEBHOOK_ID`, `DISCORD_WEBHOOK_TOKEN`은 secret으로 취급한다. 실제 `.env` 값은 로그/문서/Notion에 기록하지 않는다.
- `compatibility_constraints`: package.json은 ESM(`type: module`)이고 Node의 `--experimental-transform-types` 실행 경로를 사용한다.
- `project_specific_notes`: 현재 저장소에는 기존 애플리케이션 코드와 테스트가 있으므로 harness 적용은 운영/검증 계층을 추가하는 방식으로 유지한다. 기존 README, package.json, src, tests는 덮어쓰지 않았다.

## 활성 운영 선택

- `active_workflows`: agent-flow start, reference-first 조사, verify/quality-gate, closeout evidence
- `active_skills`: search-first, security-review, verification-loop, code-review-expert, tdd-workflow
- `active_rules`: secrets, git hygiene, confirmation-required, TypeScript language rules
- `validation_summary`: 기본 애플리케이션 검증은 `npm test`; harness 구조 검증은 `python3 scripts/verify-skeleton.py`; 통합 게이트는 `python3 scripts/quality-gate.py --format json`.
- `pivot_summary`: 뉴스 소스가 늘어나거나 전송 대상이 많아지면 data-pipeline 또는 service profile로 재분류한다.

## 첫 반복 체크리스트

- [x] 목표가 한 문장으로 쓰였습니다.
- [x] 성공 기준과 실패 기준이 측정 가능합니다.
- [x] 기술 스택과 제약 조건이 명확합니다.
- [x] 모르는 항목은 `[NEEDS CLARIFICATION: <specific question>]` 또는 명시적 보류용 `TBD`로 표시했습니다.
- [x] 이미 아는 경우에만 활성 스킬과 워크플로를 적었습니다.
- [x] 이미 아는 경우에만 마이크로 검증을 요약했습니다.
- [ ] 알려진 오픈소스, 경쟁 제품, 공식 문서, 기존 레퍼런스는 후보 카드로 처리했거나 명시적으로 없음/TBD로 표시했습니다.
- [x] 프로젝트별 예외가 있다면 문서화했습니다.
