# Hook Scripts

This directory contains executable hook adapters. The v1 lifecycle is light:
hooks may call internal guard/report scripts, but `scripts/agent-flow.py` stays
the only public command that agents should choose directly.

## Lifecycle Points

- Session start: run `python scripts/agent-flow.py start --format json` to
  summarize mode, pending decisions, reference task state, and next action.
- Before shell/tool calls: run `scripts/hooks/pre-tool-use-guard.py.example`
  or a project-local enabled copy. Timeout or parser failure should deny by
  default.
- After shell/edit/write calls: run `scripts/hooks/post-tool-use-log.py` to
  append normalized activity records to `runtime/activity-log.jsonl`.
- After MCP/tool responses: normalize previews and sidecar references so long
  outputs are searchable without bloating the main log.
- Session end: run `python scripts/session-snapshot.py write` after handoff
  updates so the machine-readable snapshot matches append-only ledgers.

`hooks/hooks.json` documents this lifecycle for Claude Code-style hook systems.
Codex ignores that file, so Codex agents follow the same lifecycle by invoking
the internal scripts directly when appropriate.

## Contract

Input:

- Tool/action name.
- Status.
- Affected files.
- Timestamp.
- Optional evidence pointer.
- Optional `goal_lineage`.

Output:

- One JSONL line appended to `runtime/activity-log.jsonl`.

Safety:

- Validate JSON before append when possible.
- Do not log secrets.
- Do not mutate project files other than runtime logs.
- Fail closed if path containment fails.
- Record permission decisions as audit events with project/session scope.
- Treat typed permission policy as a harness-level helper, not as a sandbox.

Example:

```powershell
python scripts/hooks/post-tool-use-log.py --tool shell_command --status completed --summary "ran smoke test" --project common-ai-architecture
```

## PreToolUse 선택 활성화 (옵션)

`pre-tool-use-guard.py.example`는 기본 비활성 템플릿입니다. 비밀정보 패턴, 위험 명령
(`rm -rf /` 등), 보호된 경로 쓰기(`.env`, `id_rsa`, `.aws/credentials` 등)를 차단합니다.

활성화 방법:

1. 파일을 `pre-tool-use-guard.py`로 이름 변경(또는 복사).
2. 하네스의 PreToolUse 훅에 등록. 예: Claude Code의 경우 `.claude/settings.local.json`의
   `hooks.PreToolUse`에 명령으로 추가.
3. 필요한 프로젝트별 패턴을 `SECRET_PATTERNS` / `DANGEROUS_COMMANDS` /
   `PROTECTED_WRITE_PATTERNS`에 추가.

동작:

- stdin으로 JSON 페이로드를 받아 일치 패턴을 검사합니다.
- 허용: `exit 0`.
- 차단: `exit 2` + stderr에 차단 이유.
- 입력 오류: `exit 1`.
- timeout 또는 정책 파일 파싱 실패는 deny-by-default로 취급합니다.
- 승인 결과는 `runtime/activity-log.jsonl`에 audit event로 남기는 것을
  권장합니다. session 범위 승인과 project 범위 승인은 구분해야 합니다.

확인:

```bash
# 허용 예시
echo '{"tool_input":{"command":"ls -la"}}' | python scripts/hooks/pre-tool-use-guard.py
# 차단 예시
echo '{"tool_input":{"command":"rm -rf /"}}' | python scripts/hooks/pre-tool-use-guard.py
```

이 가드는 **완전한 보안 경계가 아닙니다**. 일반적 실수를 잡기 위한 1차 필터이며,
권한 관리, 코드 리뷰, 샌드박스와 함께 써야 합니다.
