# News Crawling

OpenAI / Anthropic / Threads 뉴스를 감지해 본문을 요약한 뒤 Discord 웹훅으로 보내는 Node.js/TypeScript 워커입니다. 웹 대시보드에서 **어떤 소스 → 어떤 디스코드 → 어떤 주기**를 직접 관리합니다.

## 주요 동작
- 소스: OpenAI 뉴스(RSS), Anthropic 뉴스, Threads
- 요약: Groq API (`https://api.groq.com/openai/v1`)
- 본문: 상세 기사 페이지 본문만 사용
- 중복 방지: SQLite에 처리한 URL 저장
- 전송: 대시보드에서 등록한 라우트(소스 × 웹훅 × 주기)별로 독립적으로 폴링
- 대시보드: `http://localhost:3000` — 검정 계열 모던 UI

## 실행
```sh
docker compose up -d --build
```
컨테이너 안에서 `npm start`가 실행되며 워커와 대시보드가 같은 프로세스에서 함께 뜹니다. 호스트의 `localhost:3000`으로 대시보드에 접근하세요.

## 대시보드에서 관리하는 것
- **Discord Webhooks** — 라벨 + 웹훅 URL 등록/수정/삭제
- **Routes** — `(소스, 웹훅, 주기 분)` 페어. ON/OFF 토글로 일시 정지 가능
- **Settings** — Groq API 키 저장 / 제거, "전체 초기화"

라우트가 0개거나 모두 OFF면 워커는 아무것도 보내지 않습니다.

## 환경 변수 (선택)
모두 옵셔널입니다. 비밀값은 대시보드에서 관리하는 것을 권장합니다.

- `GROQ_API_KEY`: 대시보드에 저장된 키가 없을 때만 폴백으로 사용
- `GROQ_MODEL` / `GROQ_MODEL_FALLBACKS`: 요약 모델 (기본 `openai/gpt-oss-120b`)
- `SUMMARY_MAX_CHARACTERS`: 기본 `1800`
- `LOG_LEVEL` / `LOG_FORMAT`: `info` / `pretty`
- `SQLITE_PATH`: 상태 DB 경로 (기본 `./data/news-crawling.sqlite`)
- `DASHBOARD_HOST` / `DASHBOARD_PORT`: 기본 `0.0.0.0:3000`

> 과거에 사용하던 `DISCORD_WEBHOOK_URL`, `DISCORD_WEBHOOK_ID/TOKEN`, `POLL_INTERVAL_MINUTES`는 더 이상 사용되지 않습니다.

## 테스트 모드 (CLI)
대시보드 없이 한 번만 발송해보고 싶을 때:
```sh
npm run top -- --top-count 2
npm run top -- --latest
npm run top -- --focus-url https://openai.com/index/our-approach-to-the-model-spec/
```
대시보드에 등록된 첫 번째 웹훅으로 전송합니다(없으면 발송 스킵).

## 테스트
```sh
npm test
```
