# News Crawling

OpenAI 뉴스 RSS를 감지해 새로운 글이 올라오면 본문을 요약한 뒤 Discord 웹훅으로 보내는 Node.js/TypeScript 워커입니다.

## 주요 동작
- 소스: `https://openai.com/news/rss.xml`
- 요약: Groq API (`https://api.groq.com/openai/v1`)
- 본문: 상세 기사 페이지 본문만 사용
- 중복 방지: SQLite에 처리한 URL 저장
- 현재 전송 대상: **테스트 웹훅만 사용** (`TEST_DISCORD_WEBHOOK_URL`)
  - `DISCORD_WEBHOOK_URL`은 설정해 둬도 현재 운영에서는 보내지지 않습니다.

## 실행 환경 변수
- `GROQ_API_KEY` (필수): Groq API Key
- `GROQ_MODEL` (기본값: `openai/gpt-oss-20b`)
- `SUMMARY_MAX_CHARACTERS` (기본값: `400`, 현재 시스템 기본 테스트 기준)
- `TEST_DISCORD_WEBHOOK_URL`: **실제로 보낼 테스트 웹훅 URL**
- `DISCORD_WEBHOOK_URL` 또는 `DISCORD_WEBHOOK_ID` + `DISCORD_WEBHOOK_TOKEN`: 프로덕션 용도로 보관용(현재는 미사용)
- `TOP_TEST_ARTICLE_COUNT`: 테스트 시 기본 상위 개수 (기본 `2`)
- `TOP_TEST_REFERENCE_URL`: 선택, 특정 URL 우선 정렬용
- `POLL_INTERVAL_MINUTES`: 워커 주기(기본 `10`)
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

## 테스트
```powershell
npm test
```
