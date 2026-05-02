---
status: done
created_at: 2026-05-02T12:32:42Z
replan_count: 0
supersedes: null
depends_on: []
---

# 0001 - Harness Integration

## Goal

기존 News_Crawling 프로젝트에 AI_architecture 공용 뼈대 시스템을 적용한다.

## Completed

- 기존 `README.md`, `package.json`, `src/`, `tests/`, `.env.example`은 덮어쓰지 않았다.
- 임시 부트스트랩 프로젝트를 생성해 project-specific profile/state를 seed했다.
- canonical `config`, `docs`, `scripts`, `skills`, `agents`, `rules`, `runtime`, `schemas`, `plans`, `state` 계층을 추가했다.
- `scripts/convert.py`로 `.codex/`, `.claude/`, `.mcp.json`, `CLAUDE.md` generated artifact를 재생성했다.
- 프로젝트 프로필, 프로젝트 명세, 런타임 시작 계약을 News_Crawling 기준으로 채웠다.

## Verification

- `python3 scripts/verify-skeleton.py --root .`: passed before project-specific docs update.
- 추가 검증은 적용 완료 후 `verify.py`, `quality-gate.py`, `npm test`로 이어간다.
