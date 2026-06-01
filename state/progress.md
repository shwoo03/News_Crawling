# Progress

## 현재 마일스톤
GitHub `.env` 노출 히스토리 정리 완료

## 완료된 작업
- 골격 부트스트랩
- 사용자가 제공한 Discord 웹훅을 `DISCORD_WEBHOOK_URL` 단일 설정으로 정리했다.
- 로컬 `.env`에는 실행 필수값인 `GROQ_API_KEY`와 `DISCORD_WEBHOOK_URL`만 남겼다.
- `.env`를 git 추적에서 제거했다.
- Docker 이미지 `news_crawling-news-crawler:latest`를 빌드했다.
- Docker 컨테이너에서 `node --experimental-transform-types src/index.ts --top --latest`를 실행해 OpenAI, Anthropic, Threads 최신 1건씩 Discord 전송을 확인했다.
- Groq 요약을 구조화 JSON 브리핑으로 변경했다.
- Discord embed를 `뉴스 브리핑`, `한눈에 보기`, `왜 중요할까`, `출처`, `발행 시각` 포맷으로 변경했다.
- 기본 `SUMMARY_MAX_CHARACTERS`를 1200자로 올렸고, 이후 Threads 상세 브리핑 요구에 맞춰 1800자로 확장했다.
- Docker 컨테이너에서 전체 Node 테스트 15개 통과를 확인했다.
- 새 포맷으로 OpenAI, Anthropic, Threads 최신 1건씩 Discord 전송을 확인했다.
- Threads 상세 페이지 수집을 렌더링된 `body.innerText` 기반으로 바꾸고, 작성자 `choi.openai`의 전체 번호 스레드를 우선 추출하게 했다.
- 번호가 없는 Threads 글은 첫 작성자 연속 구간만 보수적으로 수집하고, 실패 시 기존 HTML 단일 본문 추출로 fallback하게 했다.
- 브리핑 상세도를 summary 3개, highlights 5개, importance 3개로 늘리고 기본 `SUMMARY_MAX_CHARACTERS`를 1800자로 올렸다.
- Discord embed 설명/필드에 길이 제한을 적용했다.
- Docker 컨테이너에서 전체 Node 테스트 17개 통과를 확인했다.
- 리빌드된 Docker 이미지에서 실제 Threads 최신 글 본문 길이 2859자와 `1/`, `2/`, `7/` 포함을 확인했다.
- Docker 컨테이너에서 OpenAI, Anthropic, Threads 최신 1건씩 Discord 웹훅 전송을 확인했다.
- GitHub `main` 히스토리에서 `.env` 경로를 제거했다.
- 원격 `main`을 `2f2ce87`에서 `.env` 제거 히스토리인 `a5175f1`로 `--force-with-lease` 갱신했다.
- `git log --all -- .env`, `git rev-list --objects --all | rg '(^| )\\.env$'`, `git ls-tree -r HEAD --name-only | rg '^\\.env$'`에서 `.env` 경로가 없음을 확인했다.
- `python3 scripts/security-scan.py --strict`에서 critical/high/medium/low/info 모두 0건을 확인했다.

## 다음 작업
- GitHub에 노출됐던 `.env` 값은 폐기된 것으로 보고 `GROQ_API_KEY`와 Discord Webhook 관련 secret을 교체한다.
- README와 프로젝트 프로필은 현재 OpenAI 중심 설명이라, Anthropic/Threads까지 반영하도록 별도 문서 갱신을 검토한다.
- `python3 scripts/verify-skeleton.py`는 현재 `CLAUDE.md` 누락과 `.claude-plugin/plugin.json` entrypoint 불일치 때문에 실패하므로 별도 harness 정리가 필요하다.
