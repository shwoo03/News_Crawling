# News Crawling

OpenAI 뉴스 RSS를 감지해 새로운 글이 올라오면 본문을 요약한 뒤 Discord 웹훅으로 보내는 Node.js/TypeScript 워커입니다.

## 주요 동작
- 소스: `https://openai.com/news/rss.xml`
- 요약: Groq API (`https://api.groq.com/openai/v1`)
- 본문: 상세 기사 페이지 본문만 사용
- 중복 방지: SQLite에 처리한 URL 저장
- 전송 대상: `DISCORD_WEBHOOK_URL`
- 워커 실행 시 즉시 1회 확인 후, 기본값으로 10분마다 새 글을 다시 확인

## 실행 환경 변수
- `GROQ_API_KEY` (필수): Groq API Key
- `GROQ_MODEL` (기본값: `openai/gpt-oss-120b`)
- `GROQ_MODEL_FALLBACKS` (예시: `llama-3.3-70b-versatile,meta-llama/llama-4-scout-17b-16e-instruct`)
- `SUMMARY_MAX_CHARACTERS` (기본값: `800`)
- `DISCORD_WEBHOOK_URL` 또는 `DISCORD_WEBHOOK_ID` + `DISCORD_WEBHOOK_TOKEN`: 실제 Discord 전송 대상
- `TOP_TEST_ARTICLE_COUNT`: 테스트 시 기본 상위 개수 (기본 `2`)
- `TOP_TEST_REFERENCE_URL`: 선택, 특정 URL 우선 정렬용
- `POLL_INTERVAL_MINUTES`: 워커 주기(기본 `10`, 도커 배포 시 10분마다 전송 확인)
- `LOG_LEVEL`: `debug` | `info` | `warn` | `error`
- `LOG_FORMAT`: `pretty` | `json`
- `SQLITE_PATH`: 상태 DB 경로 (기본 `./data/news-crawling.sqlite`)

## 사용법
```powershell
# 실시간 폴링 실행
npm start

# 테스트 모드(한 번 실행)
npm run top

# 최신 글 1개만 테스트
npm run top -- --latest

# 상위 2개 테스트 + 특정 URL 우선 정렬
npm run top -- --top-count 2 --focus-url https://openai.com/index/our-approach-to-the-model-spec/
```

## 로그
- 가독성 높게 보려면 `LOG_FORMAT=pretty`
- 파싱/수집 모니터링이나 알림 연동용은 `LOG_FORMAT=json`

## Docker
```powershell
docker compose up -d --build
```

`docker compose`로 올리면 컨테이너 안에서 `npm start`가 실행되고, 앱이 계속 살아 있으면서 `POLL_INTERVAL_MINUTES=10` 기준으로 새 글을 확인해 Discord 웹훅으로 전송합니다.

Groq 요약 모델은 기본적으로 `openai/gpt-oss-120b`를 먼저 쓰고, 레이트리밋(`429`)이 나면 `GROQ_MODEL_FALLBACKS`에 적은 순서대로 자동 전환합니다.

## 테스트
```powershell
npm test
```
