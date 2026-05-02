# 임시 파일 규칙

## 한 문장 정의

이 문서는 작업 중 만드는 스크래치·디버그·테스트 파일의 네이밍과 수명 규칙입니다.

## 무엇을 하는가

에이전트와 사람이 작업 중 "잠깐만 쓸" 파일을 만들 때(디버그 스크립트, 재현 케이스, 중간 출력) 프로젝트에 쓰레기가 쌓이지 않도록 이름과 수명 기준을 정합니다. 별도 청소 스크립트는 없습니다. 규칙으로 관리합니다.

## 왜 필요한가

감사 라운드에서 반복적으로 "임시 테스트 파일이 뼈대에 남아 있다"는 문제가 나왔습니다(예: `runtime/tmp-regex2.py`, 루트의 `Users/` 폴더). 파일이 남으면 (a) 다음 세션이 뭐하는 파일인지 추측해야 하고, (b) bootstrap이 새 프로젝트로 복사해 확산되며, (c) grep·검색 결과가 시끄러워집니다.

## 네이밍 규칙

작업 중 일시적으로만 필요한 파일은 **접두사**로 표시합니다.

- `tmp-<설명>.<확장자>`: 짧은 수명, 이 세션 안에서만 씁니다.
- `scratch-<설명>.<확장자>`: 실험·탐색용, 결과가 나오면 버립니다.
- `<설명>-smoke-<랜덤값>`: 테스트가 자동 생성한 임시 디렉터리나 파일입니다.

예: `tmp-regex-test.py`, `scratch-benchmark.md`, `tmp-round25-log.py`.

접두사 없는 이름(`debug.py`, `test.md`, `foo.py`)은 임시 파일로 인정되지 않습니다. 이름이 일반적이면 다른 사람이 실수로 건드릴 수 있습니다.

## 위치

- 기본 위치: `runtime/` 아래(예: `runtime/tmp-foo.py`). `runtime/` 은 이미 런타임 영역이므로 소스와 섞이지 않습니다.
- 외부 오픈소스 repo clone 원본은 `runtime/external-repos/` 아래에 둡니다. 이는 임시 스크래치 파일은 아니지만 런타임 분석 산출물이므로 새 프로젝트로 복사하지 않습니다.
- 허용 위치: 어느 디렉터리든 접두사만 지키면 허용합니다. 그러나 `docs/`, `rules/`, `knowledge/` 같은 **문서 영역**에는 되도록 두지 않습니다(검색 결과 오염).
- 금지 위치: `src/`, `codex/`, `.claude/`, `knowledge/` 아래 장기 파일과 섞이지 않습니다.

## 수명

- **세션 종료 전 삭제**가 기본입니다. 세션을 종료할 시점에 `tmp-*`, `scratch-*` 파일이 남아 있으면 지웁니다.
- **절대 commit하지 않습니다**. 커밋 직전 staged 목록에 `tmp-`/`scratch-`가 보이면 unstage하거나 삭제합니다.
- 오래 보관할 가치가 있으면 **이름을 바꿔** 다른 영역으로 옮깁니다. 예: `runtime/tmp-bench-results.md` → `docs/_meta/benchmark-2026-04.md`.

## Bootstrap과의 관계

- `scripts/bootstrap/new-project.py`는 `SKIP_NAME_PREFIXES = ("tmp-", "scratch-")`와 `SKIP_NAME_CONTAINS = ("-smoke-",)`로 **이 접두사/패턴의 파일과 디렉터리를 새 프로젝트에 복사하지 않습니다**. 즉, 뼈대에 잠깐 남겨둬도 새 프로젝트로는 전파되지 않습니다.
- `runtime/external-repos/`는 README만 보존하고 clone 원본은 새 프로젝트에 복사하지 않습니다. 외부 repo 분석 결과는 후보 카드와 dry-run 제안에 남겨야 합니다.
- 그래도 뼈대 자체의 위생을 위해 세션 종료 전 지우는 것을 원칙으로 합니다.

## 수동 정리

세션 종료 전 다음 명령으로 남은 임시 파일을 확인합니다(셸에 맞게 선택).

```bash
# POSIX
find . -type f \( -name 'tmp-*' -o -name 'scratch-*' \) -not -path './runtime/archive/*'
```

```powershell
# Windows PowerShell
Get-ChildItem -Recurse -Force | Where-Object { $_.Name -match '^(tmp|scratch)-|-smoke-' }
```

목록을 확인한 뒤 필요 없는 파일은 직접 삭제합니다.

## 결과는 무엇인가

이 규칙을 지키면 다음 상태를 유지합니다.

- 뼈대와 프로젝트에 쓰레기가 쌓이지 않습니다.
- 다음 세션이 "이 파일이 뭔지 추측"할 필요가 없습니다.
- 커밋 diff가 깨끗합니다.
- bootstrap이 새 프로젝트에 잡파일을 전파하지 않습니다.

## 기능 추가/수정 판단 기준

새 접두사나 임시 패턴을 추가할 이유가 충분히 반복되면(두세 프로젝트에서 공통) 이 문서에 등재하고 `scripts/bootstrap/new-project.py`의 `SKIP_NAME_PREFIXES` 또는 `SKIP_NAME_CONTAINS`와 동기화합니다. 한 프로젝트만의 접두사는 해당 프로젝트 문서에 둡니다.

## 구현 연결 정보

- 상위 규칙 인덱스: `rules/common/README.md`
- 권고 디렉터리 레이아웃: `rules/common/directory-layout.md`
- Bootstrap SKIP 규칙: `scripts/bootstrap/new-project.py`의 `SKIP_NAME_PREFIXES`, `SKIP_NAME_CONTAINS`
- 외부 repo clone 작업 공간: `runtime/external-repos/README.md`
- Bootstrap 가이드: `scripts/bootstrap/README.md`
