# Decisions (append-only)

> 형식: `## YYYY-MM-DD HH:MM — <결정 요약>` 다음 줄에 근거.
> 절대 이전 결정을 수정/삭제하지 말 것. 번복은 새 항목으로 추가.

## 2026-05-02T12:29:07Z — 골격 부트스트랩
- 사용 골격: AI_architecture canonical layer
- 모드: codex-primary (v1)
- 프로젝트: News_Crawling
- 도메인: cli
- 스택: node-typescript-playwright

## 2026-06-01T05:16:49Z — GitHub main 히스토리에서 .env 제거
- `.env`는 단일 삭제 커밋으로는 GitHub 과거 기록에 남기 때문에 모든 reachable 커밋에서 `.env` 경로를 제거하도록 히스토리를 재작성했다.
- 원격 `main`은 `--force-with-lease=main:2f2ce877f9c36876049661258de0a5c7b1cfde2f`로 기존 HEAD가 예상 커밋일 때만 `a5175f13fd58710d9a964a45a7b06699d04f0536`로 교체했다.
- 노출된 secret 값은 히스토리 정리와 별개로 폐기된 것으로 보고 교체해야 한다.
