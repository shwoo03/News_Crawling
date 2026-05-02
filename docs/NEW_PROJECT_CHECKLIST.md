# 새 프로젝트 시작 체크리스트

## 한 문장 정의

이 체크리스트는 공용 AI 아키텍처 스켈레톤으로 새 프로젝트를 만들 때 에이전트가 빠뜨리지 말아야 할 초기화 순서입니다.

## 무엇을 하는가

새 프로젝트는 수동 복사보다 `scripts/bootstrap/new-project.py`를 기준으로 만듭니다. 이 스크립트는 스켈레톤 내부 런타임 기록을 새 프로젝트로 새지 않게 제거하고, 프로젝트 프로필, 지식 인덱스, 세션 인수인계, canonical `state/`와 `plans/`를 새로 시드합니다.

## 왜 필요한가

공용 스켈레톤에는 자체 개발 로그와 후보 카드, generated artifact가 들어 있습니다. 단순 복사는 이 내부 상태를 새 프로젝트의 사실처럼 섞을 수 있습니다. 체크리스트는 새 프로젝트가 깨끗한 상태로 시작하고, Codex와 Claude가 같은 canonical source에서 출발하도록 합니다.

## Phase 1: 대상 준비

- 대상 폴더가 스켈레톤 내부가 아닌지 확인합니다.
- 이미 파일이 있는 대상이라면 `--force`가 기존 프로젝트 사실을 덮어쓰지 않는지 확인합니다.
- 프로젝트 이름, 도메인, 기술 스택, owner 값을 한 줄 값으로 준비합니다.

## Phase 2: 부트스트랩

에이전트는 다음 계약으로 새 프로젝트를 생성합니다.

```powershell
python3 scripts/bootstrap/new-project.py --name <project-name> --target <path> --domain <domain> --stack <stack> --owner <owner>
```

생성 직후 확인할 핵심 파일은 다음입니다.

- `AGENTS.md`
- `CLAUDE.md`
- `docs/PROJECT_PROFILE.md`
- `state/progress.md`
- `state/decisions.md`
- `plans/INDEX.md`
- `runtime/state/session-handoff.md`

## Phase 3: 첫 검증

에이전트는 생성된 프로젝트에서 가능한 검증을 실행합니다.

```powershell
python3 scripts/verify-skeleton.py
python3 scripts/verify-parity.py
```

검증이 실패하면 새 작업으로 넘어가지 않고 실패 원인을 `state/blockers.md` 또는 `runtime/activity-log.jsonl`에 남깁니다.

## Phase 4: 첫 대화

첫 세션은 바로 구현하지 않고 프로젝트 프로필을 채웁니다.

- 프로젝트 목표
- 성공 기준
- 실패 기준
- 제약 조건
- 외부 레퍼런스 검토 여부
- 첫 plan으로 둘 최소 작업

모르는 사실은 추측하지 않고 `[NEEDS CLARIFICATION: <질문>]` 또는 `TBD`로 남깁니다.

## Phase 5: 첫 plan

목표와 성공 기준이 정리되면 `plans/active/0001-<slug>.md`를 만들고 `plans/INDEX.md`에 등록합니다. plan에는 status, created_at, replan_count, depends_on, parent, children 같은 메타데이터를 둡니다.

첫 plan은 작아야 합니다. 보통 다음 중 하나가 적합합니다.

- 외부 레퍼런스 후보 수집
- 런타임 시작 계약 작성
- 가장 작은 smoke 구현
- 기존 프로젝트에서 가져올 candidate skill 검토

## Phase 6: 운영 시작

운영이 시작되면 다음 불변 조건을 유지합니다.

- `.codex/`, `.claude/`, `.mcp.json`은 generated artifact입니다.
- canonical source 변경 후에는 `scripts/convert.py`와 `scripts/verify-parity.py`를 실행합니다.
- skill 변경 후에는 `scripts/eval.py <skill-name>`로 골든 케이스를 확인합니다.
- 세션 종료 전 `state/progress.md`와 `runtime/state/session-handoff.md`를 갱신합니다.

## 구현 연결 정보

- 부트스트랩: `scripts/bootstrap/new-project.py`
- 구조 검증: `scripts/verify-skeleton.py`
- canonical 변환: `scripts/convert.py`
- parity 검증: `scripts/verify-parity.py`
- 운영 루프: `docs/OPERATING_LOOP.md`
- 세션 연속성: `docs/SESSION_CONTINUITY.md`
- 외부 레퍼런스 검토: `docs/REFERENCE_DISCOVERY_WORKFLOW.md`
