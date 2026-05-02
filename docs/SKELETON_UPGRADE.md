# 스켈레톤 업그레이드

## 한 문장 정의

이 문서는 공용 AI 스켈레톤이 개선됐을 때 이미 부트스트랩된 기존 프로젝트가 같은 수준으로 따라올 수 있도록 업그레이드 경로를 정리한 기준입니다.

## 무엇을 하는가

부트스트랩 이후 스켈레톤이 업데이트되면 기존 프로젝트는 자동으로 상속되지 않습니다. 이 문서는 어떤 파일을 복사해도 안전한지, 어떤 파일은 수동으로 머지해야 하는지, 어떤 파일은 절대 덮어쓰면 안 되는지를 결정하게 해 줍니다.

## 왜 필요한가

여러 프로젝트를 같은 스켈레톤에서 시작하면 시간이 지날수록 스켈레톤이 개선됩니다. 이때 업그레이드 정책이 없으면 두 가지 실패가 생깁니다. 첫째, 오래된 프로젝트가 새 규칙을 놓쳐 품질이 뒤처집니다. 둘째, 업그레이드 중 사용자가 프로젝트 고유 상태(활동 로그, 세션 인수인계, 지식 인덱스)를 덮어써서 복구 불가능한 손실이 발생합니다.

## 어떻게 동작하는가

업그레이드는 3개 영역으로 나눕니다.

### 안전하게 복사 가능한 영역

스켈레톤에서 그대로 덮어써도 되는 파일들입니다. 프로젝트 고유 상태가 없고, 스켈레톤이 canonical 소스입니다.

- `docs/ARCHITECTURE.md`, `docs/OPERATING_LOOP.md`, `docs/SESSION_CONTINUITY.md`
- `docs/THREE_LAYER_MODEL.md`, `docs/SKILL_DISTRIBUTION_MODEL.md`
- `docs/RUNTIME_EVENT_SCHEMA.md`, `docs/GOVERNANCE.md`
- `docs/WORKFLOW_CATALOG.md`, `docs/PIVOT_TRIGGERS.md`
- `docs/DOCUMENTATION_STYLE_GUIDE.md`, `docs/FEATURE_DECISION_GUIDE.md`
- `docs/NOTION_DOCUMENTATION_RULES.md`
- `docs/AGENT_REGISTRY.md`, `docs/SKELETON_UPGRADE.md`
- `docs/wiki-ops/*.md`
- `docs/_meta/*.md`
- `rules/common/**` (README 포함), `rules/languages/**` (README 포함)
- `scripts/**/*.py` (bootstrap, wiki-lint, verify-skeleton, hooks),
  `scripts/README.md`, `scripts/bootstrap/README.md`, `scripts/hooks/README.md`
- `codex/agents/README.md`, `codex/agents/codebase-explorer.md`,
  `codex/agents/implementation-worker.md`, `codex/agents/independent-validator.md`,
  `codex/agents/strategy-planner.md`
  (개별 에이전트 파일도 canonical 소스이지만, 프로젝트가 frontmatter를 수정했다면
  "수동 머지"로 재분류. 기본은 안전 복사.)
- `codex/rules/**`, `codex/skills/_template/**`, `codex/skills/README.md`,
  `codex/skills/universal/**`, `codex/workflows/_template.md`
- `examples/**` (참고용 예시, 프로젝트 고유 상태 아님)
- `CLAUDE.md`, `AGENTS.md`, `README.md`, `.editorconfig`
- `docs/README.md`, `docs/PROJECT_PROFILE.template.md`,
  `docs/PROJECT_SPEC.template.md`, `docs/PROJECT_OPERATING_PLAN.template.md`

### 수동으로 머지해야 하는 영역

프로젝트 고유 상태와 스켈레톤 구조가 섞여 있는 파일들입니다. 자동 덮어쓰기 금지. 새 필드나 섹션이 추가됐다면 diff를 보고 사용자가 병합합니다.

- `docs/PROJECT_PROFILE.md`: 스키마가 바뀌면 새 필드만 추가. 기존 값은 보존.
  구체 절차는 아래 "PROJECT_PROFILE 머지 절차" 참조.
- `docs/PROJECT_SPEC.md` (있는 경우): 같음.
- `docs/PROJECT_OPERATING_PLAN.md` (있는 경우): 같음.
- `knowledge/index.md`: 스켈레톤의 인덱스 규칙이 바뀌면 규칙 섹션만 병합. K 항목은 프로젝트 것이므로 유지.
- `.claude/settings.local.json`: 프로젝트가 승인한 권한 유지. 스키마가 바뀌면 병합.
- `.claude/settings.json` (있는 경우): 프로젝트 공용 훅/권한은 유지. 스켈레톤이 훅 필드를 추가했다면 병합.
- `codex/agents/*.md`(개별 에이전트): 역할 frontmatter 필드가 늘어나면 추가만.
  프로젝트가 해당 파일을 수정하지 않았다면 "안전 복사" 영역에서 덮어써도 됨.
- `.claude/skills/*`, `codex/skills/*` (프로젝트 스킬): 스켈레톤에 같은 이름 skill이
  새로 생기면 덮지 말고 비교 후 선택. `_template/`과 `universal/`은 제외(안전 복사).

### 의도적으로 제거된 경로 (재생성 금지)

아래 경로들은 이전 스켈레톤 버전에 존재했지만 메모리/프로모션 구조 정리 과정에서 의도적으로 제거됐습니다. `scripts/verify-skeleton.py`의 `REMOVED_PATHS`가 재등장 여부를 감시하며, 이들 중 하나라도 다시 존재하면 `removed_path_present` 에러로 실패합니다. 업그레이드 중 옛 스켈레톤에서 실수로 복사되지 않도록 주의합니다. 동일한 책임이 필요하면 기존 대체 경로를 사용하거나 새 이름의 파일을 제안하세요.

- `runtime/memory/` — 장기 메모리는 `knowledge/`(wiki)와 `runtime/state/session-handoff.md`로 분리됨.
- `codex/agents/memory-curator.md` — 메모리 큐레이션은 사람 주도 wiki-lint 흐름으로 대체됨.
- `knowledge/workflows/wiki-ingest.md` — 지식 wiki는 LLM 자동 ingest 대신 사람이 편집하는 2-op(`wiki-query`, `wiki-lint`) 구조로 전환됨. 상세 근거는 `docs/_meta/BEST_PRACTICE_GAP_IMPLEMENTATION_PLAN.md`의 G2 항목.

### 절대 덮어쓰지 않는 영역

프로젝트 고유의 실행 증거입니다. 업그레이드 중 어떤 상황에서도 덮어쓰지 않습니다.

- `runtime/activity-log.jsonl`
- `runtime/agent-runs.jsonl`
- `runtime/state/session-handoff.md`
- `runtime/validation/*`, `runtime/proposals/*`, `runtime/schedules/*` (프로젝트가 생성한 것)
- `knowledge/log.md`, `knowledge/project-registry.md`, `knowledge/lint-report.md`(린트 결과는 재생성 가능하지만 원본 내용은 보존)
- `.git/`, `.venv/`, `node_modules/`, `dist/`, `build/` (프로젝트 런타임 산출물)

### 신규 파일 분류 기본 규칙

스켈레톤 업그레이드 도중 세 영역 어디에도 명시되지 않은 새 파일을 만나면 다음 순서로 판단합니다.

1. 경로가 `runtime/`, `knowledge/`, `.claude/settings.local.json`, `docs/PROJECT_PROFILE.md`,
   `docs/PROJECT_SPEC.md`, `docs/PROJECT_OPERATING_PLAN.md` 중 하나에 속하면 → **절대 덮어쓰지 않음** 또는 **수동 머지**.
2. 경로가 `docs/`, `rules/`, `scripts/`, `codex/` 아래이고 "템플릿/규칙/예시" 성격이면 → **안전 복사**.
3. 애매하면 기본은 **수동 머지**로 취급하고 diff를 확인합니다. 자동 덮어쓰기 금지가 안전한 실패 모드입니다.
4. 스켈레톤 유지자는 새 파일을 추가할 때 **같은 커밋에서 이 문서의 세 목록 중 하나에 해당 경로를 반드시 추가**합니다. verify-skeleton이 목록 누락을 잡지는 않지만, PR 리뷰에서 "SKELETON_UPGRADE.md에 분류되었나?"가 체크 기준입니다.

## 결과는 무엇인가

이 기준을 따르면 다음 상태를 얻습니다.

- 스켈레톤의 새 규칙이 기존 프로젝트에 반영됩니다.
- 프로젝트 고유 상태는 손실되지 않습니다.
- 에이전트가 승인받아 병합해야 할 파일 목록이 명확합니다.
- 업그레이드 전후 `scripts/verify-skeleton.py`가 여전히 통과하는지로 검증 가능합니다.

## 업그레이드 절차

### 선행 조건

- 대상 프로젝트가 git으로 관리되고 있고 작업 트리가 clean 해야 합니다. 업그레이드는 다중 파일 변경이므로 되돌릴 수 있어야 합니다.
- 스켈레톤의 특정 커밋/버전을 기준으로 삼습니다. "최신"이 아니라 구체적 커밋 해시를 메모합니다.

### 단계

1. 대상 프로젝트에서 `scripts/verify-skeleton.py`가 통과하는지 먼저 확인합니다. 실패 상태에서 업그레이드하면 원인 구분이 어렵습니다.
2. 업그레이드용 브랜치를 만듭니다 (예: `git checkout -b skeleton-upgrade-<date>`).
3. 스켈레톤 체크아웃 경로를 정합니다. 예: `/tmp/skeleton-v2`.
4. 각 영역별로 diff 및 복사를 수행합니다.

   - **안전 복사 영역** — 다음 명령으로 차이를 확인합니다:
     ```
     diff -r <skeleton>/docs <project>/docs
     diff -r <skeleton>/rules <project>/rules
     diff -r <skeleton>/scripts <project>/scripts
     diff -r <skeleton>/codex <project>/codex
     diff -r <skeleton>/examples <project>/examples
     ```
     차이를 확인한 뒤 스켈레톤 버전으로 덮어씁니다. 덮어쓰기는 파일 단위로 하고, 위의 "안전 복사" 목록에 있는 경로만 대상입니다.
   - **수동 머지 영역** — 에이전트가 각 파일을 `diff`로 비교해 선택지를 요약하고, 사용자는 채팅으로 섹션 단위 승인/거절/보류를 결정합니다. `PROJECT_PROFILE.md`는 아래 별도 절차 참조.
   - **절대 덮어쓰지 않는 영역** — 건드리지 않습니다. `diff`조차 자동화하지 않습니다 (실수로 overwrite되지 않게).

5. 업그레이드 후 `scripts/verify-skeleton.py`를 다시 실행해 구조가 일관되는지 확인합니다.
6. `runtime/activity-log.jsonl`에 업그레이드 이벤트를 append합니다 (아래 "업그레이드 이벤트 포맷" 참조).
7. 변경을 커밋합니다. 커밋 메시지에 스켈레톤의 기준 커밋 해시를 기록합니다.

### PROJECT_PROFILE 머지 절차

`docs/PROJECT_PROFILE.md`는 부트스트랩 시 `PROJECT_PROFILE.template.md`로부터 생성된 후 프로젝트 고유 값으로 채워집니다. 템플릿이 진화하면 기존 프로필은 새 필드를 빠뜨리게 됩니다.

1. 스켈레톤의 새 `docs/PROJECT_PROFILE.template.md`를 엽니다.
2. 현재 프로젝트의 `docs/PROJECT_PROFILE.md`에 존재하지 않는 헤딩/필드를 찾습니다.
3. 새 필드를 프로젝트 프로필에 **빈 값 또는 `[NEEDS CLARIFICATION: <질문>]`으로 추가**합니다. 기존 값은 절대 수정하지 않습니다.
4. 제거된 필드는 남겨둡니다(삭제하지 않음). 메모로 `<!-- deprecated in skeleton vN -->`을 덧붙여 향후 정리 시 단서로 씁니다.

같은 절차를 `PROJECT_SPEC.md`, `PROJECT_OPERATING_PLAN.md`에도 적용합니다.

### 업그레이드 이벤트 포맷

`runtime/activity-log.jsonl`에 다음 형태로 append:

```json
{"ts":"<ISO8601 UTC>","phase":"maintenance","action":"skeleton_upgraded","project":"<name>","goal_lineage":["maintenance","<project>","follow skeleton improvements"],"data":{"from_commit":"<old>","to_commit":"<new>","regions_touched":["safe_copy","manual_merge"]}}
```

## 버전 마커와 스키마 호환성

현재 스켈레톤은 명시적 `skeleton_version` 또는 `schema_version` 필드를 파일에 쓰지 **않습니다**. 의도적입니다 — 매 편집마다 버전을 올리면 유지보수 비용이 높고, 스켈레톤은 완전히 새로 복사하는 방식(또는 이 문서의 절차)으로 드리프트를 잡습니다. 대신 아래 규약을 따릅니다.

- **기준점은 git 커밋 해시**: 스켈레톤은 자체 git 저장소이므로 "어느 커밋에서 부트스트랩했는지"를 프로젝트가 `runtime/activity-log.jsonl`의 bootstrap 이벤트에 기록하거나 `docs/PROJECT_PROFILE.md`의 `created_at` 근처에 메모합니다.
- **활동 로그 스키마 변경 시**: `docs/RUNTIME_EVENT_SCHEMA.md`가 canonical 정의입니다. 필드가 추가되기만 하고 기존 필드 의미는 유지된다는 것이 현재 규약입니다. 기존 로그 라인은 읽을 때 누락 필드를 `null`로 취급합니다. 기존 필드의 의미가 바뀌면 새 `action` 이름을 도입하고 옛 필드는 유지합니다. 읽는 쪽은 `ts`/`action`/`phase` 기반으로 필터해서 혼용을 처리합니다.
- **스킬/에이전트 frontmatter 스키마**: 필드는 추가만, 제거 금지. `verify-skeleton.py`의 `AGENT_REQUIRED_FIELDS`가 현재 필수 집합입니다. 이 집합이 늘면 기존 프로젝트의 에이전트 파일에 수동 병합이 필요하므로, 확장 시 이 문서와 `AGENT_REGISTRY.md`에 동시 기재합니다.

이 정책의 한계는 명시적입니다: 자동화가 모든 의미 충돌을 해결하지는 않습니다. 대신 `verify-skeleton.py`와 `quality-gate.py`가 구조·검증 수준에서 잡고, upgrade runbook이 의미 수준의 사용자 승인 지점을 고정합니다.

## 자동화 현황

`scripts/upgrade-from-skeleton.py`는 기존 프로젝트를 dry-run으로 점검하고, 승인된 안전 파일만 적용하는 자동화 경로입니다. `scripts/bootstrap/new-project.py --force`는 greenfield 재시드용이므로 기존 프로젝트 업그레이드에는 쓰지 않습니다.

업그레이드 원칙은 변하지 않습니다: 먼저 dry-run diff를 보고, risky 변경은 proposal/review queue로 남기며, 승인 후에만 파일을 반영합니다. 적용 뒤에는 `python3 scripts/verify.py`와 `python3 scripts/quality-gate.py --format json`을 실행합니다.

## 기능 추가/수정 판단 기준

- 새 파일이 추가되면 위 세 영역 중 어디에 속하는지 분류하고 이 문서의 목록에 추가합니다.
- 기존 파일의 의미가 바뀌면(프로젝트 상태가 된다든지) 영역을 재분류합니다.
- 업그레이드 도구를 자동화할 때는 먼저 dry-run 모드에서 diff만 출력하고, 승인 후에만 복사합니다.

## 구현 연결 정보

- 부트스트랩 스크립트: `scripts/bootstrap/new-project.py`
- 건강 체크: `scripts/verify-skeleton.py`
- 활동 로그: `runtime/activity-log.jsonl`
- 거버넌스 기준: `docs/GOVERNANCE.md`
## 2026-04-29 upgrade automation

`scripts/upgrade-from-skeleton.py` now provides the automated path for this runbook.

Recommended flow:

1. Inspect existing projects without changing files:
   `python3 scripts/upgrade-from-skeleton.py --projects-root C:\Users\dntmd\Desktop\Projects`
2. Apply only safe missing files:
   `python3 scripts/upgrade-from-skeleton.py --projects-root C:\Users\dntmd\Desktop\Projects --apply --safe-only`
3. Review risky changed files manually. Do not overwrite project-specific files unless the user explicitly approves:
   `python3 scripts/upgrade-from-skeleton.py --target <project> --apply --include-risky`

Safe-only mode copies missing templates and README-style support files. It does not overwrite changed `AGENTS.md`, project profiles, runtime logs, handoff files, knowledge logs, local settings, generated artifacts, or cloned external repositories.

## 자동화 실행 원칙

스켈레톤 업그레이드도 사용자가 직접 diff 명령을 실행하거나 파일을 머지하는 절차가 아닙니다. 문서 안의 diff, verify, upgrade 명령은 에이전트가 수행해야 하는 운영 절차입니다.

위험한 병합 지점에서는 에이전트가 차이를 요약하고 승인 선택지를 제시합니다. 사용자는 채팅으로 승인, 거절, 보류, 방향 수정을 말합니다. 승인 후 실제 파일 반영, 검증 실행, 활동 로그 기록, 세션 인수인계 갱신은 에이전트가 수행합니다.
