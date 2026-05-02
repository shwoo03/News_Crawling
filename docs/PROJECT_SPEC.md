# 프로젝트 명세: News_Crawling

## 한 문장 정의

News_Crawling은 OpenAI 뉴스 RSS를 감시하고 새 기사 본문을 요약해 Discord로 보내는 CLI/worker 프로젝트다.

## 무엇을 하는가

RSS에서 후보 기사를 찾고, 상세 페이지 본문을 수집하고, Groq API로 요약하고, Discord Webhook으로 발송하며, SQLite에 처리한 URL을 저장해 중복 전송을 막는다.

## 왜 필요한가

수동으로 OpenAI 뉴스 페이지를 확인하지 않아도 새 글을 빠르게 파악하고, 요약된 형태로 알림 채널에 축적할 수 있다.

## 문제 정의

- `user_problem`: OpenAI 새 글을 놓치거나, 매번 직접 열어보고 요약해야 한다.
- `current_state`: Node/TypeScript 워커와 테스트가 존재하며, harness 운영 계층을 새로 적용했다.
- `desired_state`: 코드 변경 시 애플리케이션 테스트와 harness gate가 함께 통과하고, 운영자가 자연어로 다음 작업을 지시해도 agent-flow가 목표에서 벗어나지 않는다.
- `why_now`: 기존 프로젝트에 공용 AI 운영 시스템을 적용해 이후 유지보수, 레퍼런스 조사, 검증, closeout을 일관화한다.

## 가설

| ID | 가설 | 필요한 증거 | 상태 |
| --- | --- | --- | --- |
| H1 | RSS/상세 페이지 파싱은 현재 테스트 fixture 기준으로 안정적이다. | `npm test` 통과 | untested |
| H2 | Groq/Discord secret 없이도 단위 테스트와 harness 검증은 실행 가능하다. | `npm test`, `verify-skeleton`, `quality-gate` 결과 | untested |
| H3 | 워커 운영 실패는 로그와 completion evidence로 다음 세션에 전달될 수 있다. | runtime handoff/snapshot 갱신 | seeded |

## 인터페이스 계약

### 입력

- OpenAI RSS feed
- OpenAI 기사 상세 페이지 HTML
- 환경 변수: `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_MODEL_FALLBACKS`, `DISCORD_WEBHOOK_URL` 또는 ID/token 조합, `SQLITE_PATH`
- CLI flags: `--top`, `--latest`, `--top-count`, `--focus-url`

### 출력

- Discord Webhook message
- structured/pretty log output
- SQLite processed URL state
- test/harness validation report

### 부작용

- `data/news-crawling.sqlite` 또는 `SQLITE_PATH`에 상태 저장
- Discord Webhook 호출
- Groq API 호출

### 데이터 저장

- SQLite는 중복 전송 방지 상태 저장소다.
- `.env`는 secret 저장소이며 문서/로그에 값이 복사되면 안 된다.

## 수용 테스트

| ID | 시나리오 | Given | When | Then | Measurable Outcome | 검증 방법 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 단위/통합 테스트 | repo checkout | `npm test` 실행 | news source tests 통과 | all node tests pass | `npm test` |
| A2 | harness 구조 검증 | skeleton overlay 적용 후 | `python3 scripts/verify-skeleton.py` 실행 | required paths/schema 통과 | zero errors | `python3 scripts/verify-skeleton.py --root .` |
| A3 | 운영 게이트 | skeleton overlay 적용 후 | `python3 scripts/quality-gate.py --format json` 실행 | critical checks 통과 | no FAIL status | quality gate JSON |
| A4 | 단발 실행 | 유효한 Groq/Discord 설정 | `npm run top -- --latest` 실행 | 최신 기사 1개 요약/전송 | one successful send or explicit logged failure | runtime logs |

## 반례

| ID | 반례 | 실패 이유 |
| --- | --- | --- |
| C1 | `GROQ_API_KEY` 없이 워커가 성공처럼 종료 | 필수 설정 누락을 성공으로 오인 |
| C2 | 같은 URL이 여러 번 Discord로 전송 | SQLite 중복 방지 실패 |
| C3 | `.env` 실제 값이 로그, 문서, Notion에 남음 | secret hygiene 실패 |
| C4 | harness 적용 과정에서 기존 README/package/src/tests가 덮어써짐 | 기존 프로젝트 본체 훼손 |

## 명시적 비목표

- 웹 UI 구축
- 모든 AI 회사 뉴스 통합
- Discord 외 다중 알림 채널 일반화
- 자동 외부 코드 도입

## 제약 조건

- `security`: secret은 `.env` 또는 외부 secret manager에만 둔다.
- `privacy`: API key와 webhook token은 redaction 대상이다.
- `performance`: 기본 polling interval은 10분이며 과도한 요청을 피한다.
- `compatibility`: Node ESM과 `--experimental-transform-types` 실행 방식을 유지한다.
- `cost`: Groq API 호출은 외부 비용/쿼터 영향을 받을 수 있다.

## 검증 게이트

- `micro_gate`: `npm test`
- `medium_gate`: `python3 scripts/verify-skeleton.py --root .` + `python3 scripts/verify-parity.py --root .`
- `full_gate`: `python3 scripts/quality-gate.py --format json` + 필요 시 `npm run top -- --latest`

## 추적성

| 결정 | 관련 가설 | 관련 수용 테스트 | 증거 |
| --- | --- | --- | --- |
| 기존 프로젝트에는 bootstrap force 대신 overlay copy + convert 적용 | H2, H3 | A2, A3 | runtime/activity-log.jsonl |
| 기존 README/package/src/tests는 덮어쓰지 않음 | H2 | C4 | git diff/status |

## 기능 추가/수정 판단 기준

뉴스 소스, 전송 대상, 요약 모델, 저장소 스키마, retry 정책을 바꾸는 변경은 이 명세의 입력/출력/부작용과 수용 테스트를 함께 갱신한다.
