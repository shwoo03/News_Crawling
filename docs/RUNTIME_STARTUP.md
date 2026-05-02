# Runtime Startup: News_Crawling

## 한 문장 정의

News_Crawling의 실행, 테스트, 운영 확인 명령을 고정한 런타임 계약이다.

## 필수 환경 변수

- `GROQ_API_KEY`: 필수. Groq API key.
- `DISCORD_WEBHOOK_URL` 또는 `DISCORD_WEBHOOK_ID` + `DISCORD_WEBHOOK_TOKEN`: Discord 전송 대상. 테스트/개발에서는 비워둘 수 있지만 실제 전송은 되지 않는다.
- 선택: `GROQ_MODEL`, `GROQ_MODEL_FALLBACKS`, `SUMMARY_MAX_CHARACTERS`, `TOP_TEST_ARTICLE_COUNT`, `TOP_TEST_REFERENCE_URL`, `POLL_INTERVAL_MINUTES`, `LOG_LEVEL`, `LOG_FORMAT`, `SQLITE_PATH`.

## 로컬 명령

```bash
npm test
npm run top
npm run top -- --latest
npm start
```

## Docker 명령

```bash
docker compose up -d --build
```

## Harness 명령

```bash
python3 scripts/agent-flow.py start --goal "News_Crawling 작업 시작" --format json
python3 scripts/verify-skeleton.py --root .
python3 scripts/verify-parity.py --root .
python3 scripts/quality-gate.py --format json
```

## 성공 상태

- `npm test`가 통과한다.
- `verify-skeleton`과 `verify-parity`가 통과한다.
- `quality-gate`에 FAIL이 없다.
- 실제 전송 테스트는 secret이 설정된 환경에서만 수행한다.

## 실패 신호

- `GROQ_API_KEY is required.`가 나오면 secret 설정이 누락된 것이다.
- Discord 전송 실패가 반복되면 webhook URL/ID/token을 확인한다.
- SQLite write error가 나오면 `SQLITE_PATH`와 `data/` 권한을 확인한다.
- `.env` 값이 로그나 문서에 노출되면 즉시 회전한다.
