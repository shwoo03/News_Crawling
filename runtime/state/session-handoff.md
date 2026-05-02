# Session Handoff

## Last Updated

2026-05-02T13:27:44Z

## Current Task

Threads 전체 스레드 본문 추출과 상세 브리핑 포맷을 개선하고 Docker에서 검증했다.

## Last Completed

- Groq 요약 결과를 구조화 JSON 브리핑으로 파싱하도록 변경했다.
- Discord embed를 `뉴스 브리핑`, `한눈에 보기`, `왜 중요할까`, `출처`, `발행 시각` 필드 구조로 변경했다.
- `SummaryResult`에 구조화 브리핑 필드를 추가하고 기존 `summaryKo`/`charCount`는 유지했다.
- 기본 `SUMMARY_MAX_CHARACTERS`를 1200자로 변경했다.
- Anthropic list parser가 nested subject span을 놓치는 기존 결함을 수정했다.
- `plans/done/0002-discord-news-briefing-format.md`를 완료 처리했다.
- `ThreadsNewsAdapter.fetchArticle()`가 렌더링된 `body.innerText`를 함께 읽고 작성자 `choi.openai` 본문 블록을 우선 추출하도록 변경했다.
- 번호가 있는 Threads 글은 도입 포스트와 `1/`, `2/`, `3/` 순번 본문을 이어 붙이고, 번호가 없는 글은 첫 작성자 연속 구간만 보수적으로 수집한다.
- 전체 스레드 추출이 비어 있으면 기존 HTML 단일 본문 추출로 fallback한다.
- 브리핑 상세도를 summary 3개, highlights 5개, importance 3개로 늘리고 기본 `SUMMARY_MAX_CHARACTERS`를 1800자로 변경했다.
- Discord embed 설명/필드 길이 제한을 추가했다.
- `plans/done/0003-threads-full-thread-briefing.md`를 완료 처리했다.

## Validation

- `docker compose build news-crawler`: passed.
- `docker compose run --rm --no-deps -v /Users/shwoo/mydir/Project/News_Crawling/src:/app/src:ro -v /Users/shwoo/mydir/Project/News_Crawling/tests:/app/tests:ro news-crawler node --experimental-transform-types --test tests/*.test.ts`: 17 passed, 0 failed.
- `docker compose run --rm --no-deps news-crawler node --experimental-transform-types src/index.ts --top --latest`: passed; all 3 sources reported `deliveryStatus=sent`.
  - `openai-news`: `Introducing Advanced Account Security`, summaryLength=`736`
  - `anthropic-news`: `Claude for Creative Work`, summaryLength=`806`
  - `threads-news`: `Thread post DX1h2PFCgVH`, summaryLength=`777`
- Rebuilt Docker image with the latest Threads fallback logic.
- Rebuilt image extraction check: latest Threads selected `https://www.threads.com/@choi.openai/post/DX1hrw1CvrK/`, bodyLength=`2859`, `hasThread1=true`, `hasThread2=true`, `hasThread7=true`.
- `docker compose ps -a`: no containers left running.
- `python3 -m unittest discover -s tests -v`: failed only at `test_quality_gate_json_is_parseable_without_recursive_tests` because current quality gate detects local `.env` as a HIGH secret-like assignment.
- `python3 scripts/security-scan.py --strict`: still expected to fail while local `.env` exists with a secret-like assignment.

## Recommended Next Step

1. 커밋 전 `git status`에서 `.env`가 삭제로 staged/untracked 상태인지 확인하고, 실제 commit에는 `.env` 내용이 포함되지 않게 한다.
2. strict 보안 스캔을 통과해야 하면 Docker 실행용 secret을 `.env` 밖으로 옮기거나, 로컬 secret 파일을 제거한 뒤 환경 변수 주입 방식으로 재실행한다.
3. README와 프로젝트 프로필의 OpenAI 중심 설명을 Anthropic/Threads와 새 Threads 전체 스레드 수집 정책까지 반영하도록 갱신한다.

## Open Questions / Blockers

- 로컬 `.env`가 남아 있는 동안 `python3 scripts/security-scan.py --strict`는 HIGH로 실패한다.
- 사용자가 로컬 Node 실행을 원하지 않아 Docker 기준으로 테스트했다. Homebrew Node 설치는 중단 직전 완료됐지만, 앱 검증에는 사용하지 않았다.

## Files Touched This Session

- `.env` local contents changed and removed from git tracking.
- `.env.example`, `README.md`
- `src/config.ts`, `src/types.ts`
- `src/services/summarizer.ts`, `src/services/discord.ts`
- `src/sources/anthropic-news.ts`
- `src/sources/threads-news.ts`
- `tests/openai-news.test.ts`, `tests/threads-news.test.ts`
- `plans/INDEX.md`, `plans/done/0002-discord-news-briefing-format.md`, `plans/done/0003-threads-full-thread-briefing.md`
- `runtime/review-queue.jsonl`
- `state/progress.md`
- `runtime/state/session-handoff.md`
- Docker image/cache outside git workspace

## Key Decisions

- Discord 설정은 `DISCORD_WEBHOOK_URL` 하나만 사용한다.
- `GROQ_API_KEY`는 요약 실행 필수값이므로 `.env`에 유지한다.
- 실제 전송 테스트는 로컬 Node가 아니라 Docker 컨테이너에서 수행한다.
- 새 브리핑 포맷은 OpenAI, Anthropic, Threads 전체 소스에 동일하게 적용한다.
- 브리핑 상세도는 핵심 요약 3개, 한눈에 보기 5개, 왜 중요할까 3개로 유지한다.
- Threads 수집은 번호 스레드를 우선하고, 번호가 없으면 첫 작성자 연속 구간만 보수적으로 수집한다.

## Links

- Project root: `/Users/shwoo/mydir/Project/News_Crawling`
- Skeleton source: `/Users/shwoo/mydir/AI/AI_architecture`

## Resume Prompt

이 파일을 먼저 읽고, 이어서 `docs/PROJECT_PROFILE.md`, `docs/PROJECT_SPEC.md`, `docs/RUNTIME_STARTUP.md`, `runtime/activity-log.jsonl`의 최근 30줄을 확인한다. 다음 사용자 요청이 자연어 목표라면 `scripts/agent-flow.py start --goal "<goal>" --format json`으로 mode와 next action을 먼저 확인한다.
