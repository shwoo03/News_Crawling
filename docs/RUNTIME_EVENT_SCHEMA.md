# 런타임 이벤트 스키마

## 한 문장 정의

런타임 이벤트 스키마는 에이전트 실행, 도구 사용, 검증, 예산, 목표 계보를 JSONL 로그로 남기기 위한 기록 형식입니다.

## 무엇을 하는가

이 문서는 실행 중 생긴 사건을 어떤 필드로 기록할지 정합니다. 로그는 append-only로 다루며, Codex, Claude, 훅, 검증기, Notion 문서가 같은 증거를 읽을 수 있게 합니다.

핵심 계약은 `schemas/`에도 JSON schema 스타일 문서로 고정합니다. v1 검증은 외부 패키지 없이 `scripts/schema-check.py`가 수행하며, 문서와 실제 runtime/plugin/config 파일의 필수 필드 드리프트를 빠르게 잡는 보조 게이트입니다.

## 왜 필요한가

대화 기록만으로는 프로젝트 상태를 안정적으로 이어받기 어렵습니다. 어떤 작업을 했는지, 어떤 검증을 했는지, 어떤 에이전트가 어떤 목표 때문에 실행됐는지 구조화된 로그가 있어야 다음 세션이 추측하지 않고 이어갈 수 있습니다.

## 어떻게 동작하는가

활동 로그는 일반 작업과 도구 사용을 기록합니다. 에이전트 실행 로그는 반복 에이전트가 실행될 때 역할, 목표 계보, 예산, 체크아웃 상태, 산출물을 기록합니다.

두 로그는 **파일별로 필드가 분리**됩니다. 읽는 쪽은 파일 이름으로 스키마를 결정하고, 같은 파일 안에서는 지정된 필드만 사용합니다.

| 파일 | 주 필드 | 쓰지 않는 필드 |
| --- | --- | --- |
| `runtime/activity-log.jsonl` | `action`, `phase`, `goal_lineage`, `tool_call`, `data` | `event`, `agent`, `workflow`, `artifacts` |
| `runtime/agent-runs.jsonl` | `event`, `agent`, `workflow`, `status`, `goal_lineage`, `artifacts` | `action`, `phase`, `tool_call` |
| `runtime/completion-evidence.jsonl` | `goal`, `changed_paths`, `validations`, `outcome` | `action`, `phase`, `tool_call` |
| `runtime/install-state.jsonl` | `event`, `skeleton_version`, `generated_paths`, `preserved_paths`, `validation_status` | `action`, `phase`, `tool_call` |
| `runtime/skill-usage.jsonl` | `skill`, `event`, `outcome`, `run_id`, `evidence_ref` | `action`, `phase`, `tool_call` |
| `runtime/skill-lifecycle.jsonl` | `skill`, `event`, `status`, `score`, `goldens` | `action`, `phase`, `tool_call` |
| `runtime/reference-tasks.jsonl` | `id`, `action`, `target`, `status`, `candidate_card`, `proposal`, `source_hash`, `hash_algorithm`, `retry_count`, `max_retries` | `phase`, `tool_call`, `skip_reason` |
| `runtime/checkpoints.jsonl` | `id`, `name`, `goal`, `git_sha`, `changed_paths`, `verify_status` | `action`, `phase`, `tool_call` |
| `runtime/reference-intake-cache.jsonl` | `local_path`, `source_hash`, `analysis` | `action`, `phase`, `tool_call` |
| `runtime/session-recall.sqlite` | FTS cache of activity, decisions, completion evidence, skill usage | 원본 로그 아님 |
| `runtime/tool-output-sidecars/*.txt` | 긴 tool output 원문 | JSONL 아님 |
| `state/cost-log.jsonl` | `run_id`, `agent`, `skill`, `provider`, `model`, `cost_usd` | `action`, `phase`, `tool_call` |

`ts`, `project`, `goal_lineage`는 양쪽 공통입니다. 한 엔트리가 두 필드를 동시에 담지 않습니다.

최소 활동 로그는 다음 의미를 가져야 합니다.

```json
{
  "ts": "2026-04-23T00:00:00Z",
  "phase": "implementation",
  "action": "short_action_name",
  "project": "common-ai-architecture",
  "goal_lineage": ["task", "project", "primary_goal"],
  "data": {}
}
```

긴 tool output은 activity log 안에 전부 넣지 않는다. `tool_call.summary`에는 preview만 남기고, 원문은 `runtime/tool-output-sidecars/*.txt`에 둔다.

```json
{
  "tool_call": {
    "tool": "Bash",
    "status": "completed",
    "normalized_status": "success",
    "failure_type": "",
    "empty_output": false,
    "duration_ms": null,
    "summary": "first 2000 chars...",
    "sidecar_path": "runtime/tool-output-sidecars/20260502T000000-abcd1234.txt",
    "preview_chars": 2000,
    "full_chars": 12000,
    "truncated": true
  }
}
```

에이전트 실행 로그는 가능하면 다음 정보를 포함합니다.

```json
{
  "ts": "2026-04-23T00:00:00Z",
  "event": "agent_run_started",
  "agent": "strategy-planner",
  "workflow": "system-extension",
  "project": "common-ai-architecture",
  "goal_lineage": ["task", "workflow_or_project", "primary_goal"],
  "status": "started",
  "artifacts": []
}
```

설치 상태 로그는 skeleton 복사와 canonical 변환 결과를 기록합니다.

```json
{
  "ts": "2026-05-02T00:00:00Z",
  "event": "convert_completed",
  "project": "common-ai-architecture",
  "skeleton_version": "v1.2.0",
  "source_commit": null,
  "requested_profile": "full-canonical",
  "selected_components": ["canonical"],
  "generated_paths": [".codex/skills", ".claude/skills"],
  "preserved_paths": [".claude/settings.local.json"],
  "validation_status": "verified"
}
```

`validation_status`는 `unverified`, `verified`, `failed` 중 하나입니다. `convert.py`는 generated artifact 생성 후 parity 검증 결과를 install-state에 기록합니다.

skill 사용/생명주기 로그는 `SKILL.md` frontmatter를 직접 수정하지 않고 사용량과 평가를 append-only로 남깁니다.

```json
{
  "ts": "2026-05-02T00:00:00Z",
  "skill": "research-evaluator",
  "event": "use",
  "outcome": "success",
  "run_id": "run-001",
  "goal_lineage": ["reference adoption"],
  "evidence_ref": "runtime/completion-evidence.jsonl:12"
}
```

비용 로그는 추정/실측 여부를 분리해서 남깁니다.

```json
{
  "ts": "2026-05-02T00:00:00Z",
  "run_id": "run-001",
  "agent": "researcher",
  "skill": "research-evaluator",
  "provider": "openai",
  "model": "gpt-5.5",
  "input_tokens": 12000,
  "cached_input_tokens": 0,
  "output_tokens": 1800,
  "cost_usd": 0.42,
  "cost_status": "estimated",
  "cost_source": "manual"
}
```

reference intake cache는 같은 레퍼런스를 반복 분석할 때 토큰과 시간을 아끼기 위한 append-only 캐시입니다. preview 분석은 이 파일을 쓰지 않고, `reference-intake.py --cache` 또는 후보 카드 `--write` 때만 갱신합니다.

```json
{
  "ts": "2026-05-02T00:00:00Z",
  "local_path": "/abs/path/to/reference",
  "source_hash": "sha256...",
  "analysis": {
    "name": "reference",
    "checked_revision": "abc123",
    "license": "MIT",
    "reusable_units": ["scripts", "docs"]
  }
}
```

reference task queue는 긴 reference 분석을 중단/재개할 수 있게 하는 append-only 장부입니다. 자동 실행 scheduler가 아니라 작업 상태 기록입니다.

```json
{
  "ts": "2026-05-02T00:00:00Z",
  "action": "add",
  "id": "ref-task-20260502T000000-abcd1234",
  "target": "runtime/external-repos/local/example",
  "goal": "local reference analysis",
  "candidate_card": "",
  "proposal": ""
}
```

session recall은 `runtime/session-recall.sqlite`에 생성되는 재생성 가능한 검색 캐시입니다. 원본은 항상 JSONL과 `state/decisions.md`이며, 캐시가 사라지면 `python3 scripts/session-recall.py index`로 다시 만듭니다.

`runtime/session-snapshot.json`은 사람이 읽는 `runtime/state/session-handoff.md`를 대체하지 않습니다. 다음 세션과 검증기가 빠르게 읽는 machine-readable 현재 상태입니다.

## 결과는 무엇인가

스키마를 따르면 다음이 가능해집니다.

- 다음 세션이 최근 작업을 추측하지 않습니다.
- 에이전트 실행이 상위 목표와 연결됩니다.
- 검증 결과와 실패 유형이 분리됩니다.
- 예산과 작업 소유권을 감사할 수 있습니다.
- Notion 문서나 보고서가 로그를 근거로 작성됩니다.

## 결과 분류

검증 결과는 가능한 한 아래 값으로 분류합니다.

| 값 | 의미 |
| --- | --- |
| genuine_success | 목표한 성공 기준을 충족했습니다. |
| partial_progress | 일부 진전은 있지만 성공 기준에는 부족합니다. |
| timeout | 시간 제한 때문에 결론에 도달하지 못했습니다. |
| infra_error | 도구, 환경, 네트워크 등 인프라 문제입니다. |
| blocked_by_policy | 정책이나 권한 때문에 진행하지 못했습니다. |

인프라 오류와 정책 차단은 기록에는 남기지만 품질 점수에서는 제외합니다.

`runtime/checkpoints.jsonl`은 긴 작업 중간 상태를 저장하는 append-only ledger입니다. checkpoint는 재개 위치와 검증 상태를 남기지만, 작업 완료 증거는 반드시 `runtime/completion-evidence.jsonl`에 별도로 기록합니다.

프로젝트 도메인이 추가 outcome을 필요로 하면(예: CTF의 "crashed_with_info_leak", 데이터 파이프라인의 "schema_drift") `docs/PROJECT_OPERATING_PLAN.md`의 `outcome_classification`에서 확장합니다. 표준 5개는 모든 프로젝트에 공통으로 남는 품질 메트릭 집계용 기본 분모이므로 유지하되, 프로젝트 전용 outcome은 그 위에 추가합니다.

## Timestamp 의미

`ts`는 엔트리를 **쓴 시각**이지 엄격한 논리 순서가 아닙니다. 여러 세션이나 도구가 병렬로 추가하거나 일부 초기 엔트리가 raw 값으로 기록된 경우 인접 엔트리 간 ts가 역행할 수 있습니다. 따라서:

- 이벤트 **순서**는 파일 라인 순서(append-only이므로 라인 번호)가 authoritative입니다.
- "최신 엔트리"는 마지막 라인이며, `ts` 정렬 결과가 아닙니다.
- `scripts/hooks/post-tool-use-log.py`는 새 엔트리의 ts가 마지막 엔트리 ts보다 이르면 stderr에 경고를 냅니다. 방지용 안전 장치이며 쓰기는 계속 수행합니다.

## 로그 크기 관리 정책

활동 로그와 에이전트 실행 로그는 append-only입니다. 시간이 지나면 파일이 커져 열람·파싱 비용이 증가합니다. 크기 관리는 다음 기본값을 사용합니다.

- 각 JSONL 파일이 **10,000줄을 넘으면 월 단위 아카이브**로 분리합니다.
- 아카이브 경로: `runtime/archive/activity-log-YYYY-MM.jsonl`,
  `runtime/archive/agent-runs-YYYY-MM.jsonl`.
- 아카이브는 원본 로그에서 오래된 구간만 이동하고, 원본 파일은 최근 항목만 남깁니다.
- 아카이브 이동 사실은 활동 로그에 `action: "log_archived"` 이벤트로 기록합니다.
- 아카이브 파일도 계속 append-only로 다루며, 내용을 수정하지 않습니다.
- 프로젝트가 다른 임계값을 쓰려면 `docs/PROJECT_OPERATING_PLAN.md`에 오버라이드를 적습니다.

아카이브는 `scripts/rotate-activity-log.py`로 수행합니다. 기본값은 dry-run이며 `--apply`를 붙여야 실제로 이동합니다. 10,000줄은 "슬슬 쪼개는 게 좋다"는 권고 임계값이며, 실행 시점은 사람이 판단합니다. 이 스크립트는 성공 시 활동 로그에 `action: "log_archived"` 이벤트를 남깁니다.

## 자주 쓰이는 선택 필드

활동 로그 엔트리는 기본 필드 외에 아래 선택 필드를 자유롭게 포함할 수 있습니다. 읽는 쪽은 없는 필드를 허용해야 합니다.

| 필드 | 언제 쓰나 | 예시 값 |
| --- | --- | --- |
| `tool_call` | 도구 호출 결과 기록 | `{"tool":"shell","status":"completed","summary":"..."}` |
| `automation` | 자동화 실행 모드 | `"dry-run"`, `"apply"` |
| `notion_sync` | Notion 동기화 결과 | `{"status":"ok","summary":"..."}` |
| `rule` | 규칙/정책 변경 기록 | `"draft_approved"`, `"permission_denied"` |
| `fixes` | 리팩토링 묶음 | 문자열 배열 |

새 필드는 반복해서 쓰일 때 이 표에 추가합니다. 한 번만 쓰이는 구조는 `data` 안에 둡니다.

## 기능 추가/수정 판단 기준

로그 필드를 추가하거나 수정할 때는 다음 기준을 사용합니다.

- 새 필드는 다음 결정을 돕는 증거여야 합니다.
- 기존 로그를 강제로 다시 쓰지 않습니다.
- 읽는 쪽은 오래된 로그와 최소 로그를 허용해야 합니다.
- 문자열 하나로 충분한 정보를 불필요하게 객체로 키우지 않습니다.
- 검증, 권한, 목표 계보처럼 재현성에 필요한 정보는 우선 기록합니다.
- activity-log와 agent-runs는 서로의 주 필드를 빌리지 않습니다.

## 검색

활동 로그를 필터 조건으로 빠르게 조회하려면 `scripts/search-activity-log.py`를 사용합니다. `--since/--until/--phase/--action/--project/--tool/--contains/--last` 필터를 지원하며, 기본 출력은 표이고 `--jsonl`로 원본 스트림을 얻습니다. 예시는 `scripts/README.md`의 "활동 로그 쿼리 예시" 섹션 참고.

## 구현 연결 정보

- 활동 로그: `runtime/activity-log.jsonl`
- 에이전트 실행 로그: `runtime/agent-runs.jsonl`
- 설치 상태 로그: `runtime/install-state.jsonl`
- skill 사용 로그: `runtime/skill-usage.jsonl`
- skill 생명주기 로그: `runtime/skill-lifecycle.jsonl`
- reference intake cache: `runtime/reference-intake-cache.jsonl`
- 비용 로그: `state/cost-log.jsonl`
- 세션 스냅샷: `runtime/session-snapshot.json`
- 도구 사용 로그 스크립트: `scripts/hooks/post-tool-use-log.py`
- 활동 로그 검색: `scripts/search-activity-log.py`
- 운영 루프: `docs/OPERATING_LOOP.md`

## Completion Evidence

`runtime/completion-evidence.jsonl` is the agent-owned closeout ledger. It is not a replacement for the activity log; it stores structured evidence for completed tasks so the next agent can inspect goal, changed paths, validations, outcome, residual risk, and next action without replaying the full chat.
