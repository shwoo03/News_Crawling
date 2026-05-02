# External Improvement Review - 2026-04-29

## 한 문장 정의

`runtime/external-repos/`에 clone된 외부 AI 시스템에서 현재 스켈레톤에 추가로 흡수할 만한 개선 후보를 정리한 검토 기록입니다.

## 검토 대상

- `runtime/external-repos/github.com/NousResearch__hermes-agent`
- `runtime/external-repos/github.com/nashsu__llm_wiki`
- `runtime/external-repos/github.com/affaan-m__everything-claude-code`

## 현재 결론

지금 가장 먼저 구현할 만한 개선은 `scripts/skeleton-doctor.py`입니다. 기존 `verify-skeleton.py`는 구조가 깨졌는지 확인하는 검사에 가깝고, doctor는 "이 프로젝트가 바로 문서화, 구현, 실행, 인수인계 가능한 상태인가"를 사람이 이해하기 쉽게 진단합니다.

그다음은 `runtime/review-queue.jsonl` 기반의 human review queue입니다. Notion 중복, 외부 레퍼런스 채택, 위험한 업그레이드처럼 에이전트가 혼자 결정하면 안 되는 항목을 중복 없이 모아두는 장치입니다.

## P2-A: Skeleton Doctor

### 외부 근거

- Hermes Agent: `hermes_cli/doctor.py`
  - Python 버전, venv, 필수 패키지, 환경 변수, 외부 도구, 서비스 상태를 한 번에 진단합니다.
  - 문제마다 `ok/warn/fail`과 수정 힌트를 같이 냅니다.
- Everything Claude Code: `commands/quality-gate.md`, `commands/harness-audit.md`
  - operator가 직접 실행하는 품질 게이트와 deterministic scorecard를 분리합니다.

### 스켈레톤에 맞춘 흡수 방식

직접 복사하지 않고 `concept_only + wrapper` 방식으로 흡수합니다.

새 스크립트는 다음을 확인합니다.

- `PROJECT_PROFILE.md` 또는 프로필 템플릿의 핵심 필드가 비어 있지 않은지
- `AGENTS.md`, 공통 규칙, 운영 루프, 세션 연속성 문서가 있는지
- `docs/REFERENCE_REVIEW.template.md`, `docs/RUNTIME_STARTUP.template.md`가 있는지
- 후보 카드와 reference proposal validator가 통과하는지
- `runtime/activity-log.jsonl`이 JSONL로 파싱되는지
- `runtime/state/session-handoff.md`가 있는지
- `python scripts/verify-skeleton.py`가 통과하는지
- 선택적으로 `--projects-root`를 받아 기존 프로젝트에 안전 업그레이드 누락이 있는지

### 기대 결과

새 프로젝트를 받았을 때 `python scripts/skeleton-doctor.py` 한 번으로 다음 질문에 답할 수 있습니다.

- 문서화 준비가 되었나
- 오픈소스 참고 절차가 준비되었나
- 실행 준비 문서가 준비되었나
- 로그와 인수인계가 남을 수 있나
- 기존 프로젝트로 전파 가능한 안전 업데이트가 남아 있나

## P2-B: Review Queue

### 외부 근거

- LLM Wiki: `src/stores/review-store.ts`
  - `contradiction`, `duplicate`, `missing-page`, `confirm`, `suggestion` 타입으로 사람이 판단할 항목을 모읍니다.
  - 같은 타입과 정규화된 제목이면 중복 생성하지 않고 관련 페이지와 검색어를 병합합니다.
- LLM Wiki: `src/lib/ingest-queue.ts`
  - 장기 작업을 디스크에 저장하고, 재시도, 취소, 실패 정리를 지원합니다.

### 스켈레톤에 맞춘 흡수 방식

처음부터 UI나 복잡한 큐 엔진을 만들지 않고, `runtime/review-queue.jsonl`과 `scripts/review-queue.py` 정도로 시작합니다.

초기 명령은 다음 정도면 충분합니다.

- `add`: 판단 항목 추가
- `list`: 미해결 항목 출력
- `resolve`: 선택한 조치로 해결 처리
- `dismiss`: 더 보지 않을 항목 제거

### 쓰임새

- Notion 유사 페이지가 발견되었을 때 업데이트, 대체, 공존 결정을 보류
- 외부 오픈소스 후보를 실제로 적용할지 사용자 승인 대기
- `upgrade-from-skeleton.py`에서 `update_available:risky`로 나온 항목을 추적
- 문서 간 모순이나 비어 있는 프로젝트 프로필 항목을 다음 세션으로 넘김

## P2-C: Quality Gate

### 외부 근거

- Everything Claude Code: `commands/quality-gate.md`
  - 대상 경로의 언어와 도구를 감지하고 formatter, lint, type check, remediation list를 냅니다.

### 스켈레톤에 맞춘 흡수 방식

`scripts/quality-gate.py`를 만들어 프로젝트별로 가능한 검증만 실행합니다.

- skeleton repo: `verify-skeleton.py`, reference validators, unittest
- Python 프로젝트: `python -m unittest discover` 또는 pytest 감지
- Node 프로젝트: `npm test`, `npm run build` 감지
- 문서 중심 프로젝트: stale phrase check, Notion draft quality check

## P2-D: Harness Scorecard

### 외부 근거

- Everything Claude Code: `commands/harness-audit.md`
  - 고정 rubric으로 점수를 내고 top 3 action을 제안합니다.

### 스켈레톤에 맞춘 흡수 방식

`skeleton-doctor.py --format json` 또는 별도 `scripts/skeleton-scorecard.py`로 통합할 수 있습니다.

초기 rubric 후보:

- Profile readiness
- Reference readiness
- Runtime startup readiness
- Logging and handoff readiness
- Validation readiness
- External repo hygiene
- Notion documentation readiness

## 보류 후보

### Hook Runtime Profile

Everything Claude Code의 hook profile 개념은 좋지만, 현재 스켈레톤은 hook 수가 많지 않습니다. 지금 넣으면 설정 복잡도만 늘 가능성이 큽니다. hook이 늘어난 뒤 `SKELETON_HOOK_PROFILE=minimal|standard|strict` 형태로 도입하는 것이 맞습니다.

### Persistent Task Queue

LLM Wiki의 ingest queue는 장기 작업 복구에 강합니다. 다만 현재 스켈레톤에는 먼저 review queue와 doctor가 필요합니다. 장기 Notion sync, 대량 프로젝트 업그레이드, 대량 reference review가 반복되기 시작하면 도입합니다.

## 추천 순서

1. `scripts/skeleton-doctor.py`
2. `runtime/review-queue.jsonl` + `scripts/review-queue.py`
3. `scripts/quality-gate.py`
4. `scripts/skeleton-scorecard.py`
5. hook profile / persistent task queue

## 다음 구현 제안

바로 구현한다면 P2-A부터 시작합니다. doctor는 read-only이고 기존 프로젝트를 건드리지 않으면서 현재 뼈대의 완성도를 바로 보여주기 때문에 위험 대비 효과가 가장 큽니다.
