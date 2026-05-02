# 공통 기본 규칙

## 한 문장 정의

공통 기본 규칙은 모든 프로젝트에서 에이전트가 반드시 지켜야 하는 최소 행동 기준입니다.

## 무엇을 하는가

이 규칙은 특정 도메인이나 기술 스택과 무관하게 항상 적용됩니다. 규칙은 “무엇이 반드시 참이어야 하는가”를 정하고, 구체적인 절차와 예시는 스킬이나 워크플로 문서에 둡니다.

## 왜 필요한가

프로젝트마다 목표와 기술은 달라도 안전하게 일하는 기준은 반복됩니다. 검색 없이 추측하지 않기, 작은 변경부터 검증하기, 로그를 append-only로 남기기, 모르는 사실을 만들지 않기 같은 기준은 모든 프로젝트에 필요합니다.

## 어떻게 동작하는가

에이전트는 프로젝트 프로필을 먼저 읽고, 그다음 공통 규칙을 적용합니다. 작업에 맞는 스킬이 있으면 그때만 스킬을 읽습니다. 프로젝트별 문서는 공통 규칙이나 스킬이 다루지 않는 맥락이 있을 때만 추가로 읽습니다.

## 결과는 무엇인가

공통 규칙을 적용하면 다음 상태를 유지합니다.

- 에이전트가 모르는 사실을 만들지 않습니다.
- 가장 작은 검증 가능한 변경부터 진행합니다.
- 성공 주장 전에 검증을 수행합니다.
- 로그와 지식 관리 경계가 지켜집니다.
- 프로젝트 오버레이가 얇게 유지됩니다.

## 기본 규칙

- 구조, API, 결정을 만들기 전에 먼저 검색합니다.
- 가장 작은 검증 가능한 변경을 선호합니다.
- 성공했다고 말하기 전에 검증합니다.
- 로그는 append-only로 다룹니다.
- 생성되었거나 불확실한 변경은 제안으로 둡니다.
- 장기 지식과 사용자 개인 스킬 공간은 직접 수정하지 않습니다.
- 프로젝트 오버레이는 얇게 유지합니다.
- 규칙은 짧고 재사용 가능하게 유지하고, 절차와 예시는 스킬로 보냅니다.

## 모르는 사실 표시 규칙

에이전트가 모르는 정보는 명확히 표시합니다.

- 구체적인 사용자 입력이 필요하면 `[NEEDS CLARIFICATION: <specific question>]` 형식을 사용합니다.
- 사용자가 명확히 나중으로 미룬 항목은 `TBD`로 둘 수 있습니다.
- 빈칸을 채우기 위해 사실을 만들어내지 않습니다.
- 질문 없는 `[NEEDS CLARIFICATION]` 표기는 사용하지 않습니다.
- 모든 미해결 질문을 찾는 표준 명령은 `rg "NEEDS CLARIFICATION" docs`입니다. `rg`(ripgrep)가 없으면 POSIX 환경에서는 `grep -rn "NEEDS CLARIFICATION" docs`, Windows PowerShell 환경에서는 `Select-String -Path docs\*.md -Pattern "NEEDS CLARIFICATION" -Recurse`를 사용합니다. 다른 문서는 이 명령을 참조합니다.
- 전 프로젝트 집계는 `python scripts/list-open-questions.py`를 사용합니다. `--count/--by-file/--json/--strict`(CI 게이트) 지원. 코드 펜스 안의 예시 마커는 자동 제외합니다.
- `scripts/verify-skeleton.py`도 미해결 마커 수와 잘못된 형식을 보고합니다.

## 기능 추가/수정 판단 기준

새 공통 규칙은 모든 프로젝트에 반복적으로 적용되는 불변 조건일 때만 추가합니다. 특정 작업 절차라면 스킬로 보내고, 특정 프로젝트에만 해당하면 프로젝트 프로필이나 운영 계획에 둡니다.

## 구현 연결 정보

- 검색 우선 규칙: `rules/common/search-first.md`
- 테스트 주도 작업 규칙: `rules/common/tdd-workflow.md`
- 검증 루프 규칙: `rules/common/verification-loop.md`
- 보안 리뷰 규칙: `rules/common/security-review.md`
- MCP 디스플린 규칙: `rules/common/mcp-discipline.md`
- 공통 코드 스타일: `rules/common/code-style.md`
- 권고 디렉터리 레이아웃: `rules/common/directory-layout.md`
- 임시 파일 규칙: `rules/common/ephemeral-files.md`
