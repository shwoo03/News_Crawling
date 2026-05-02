# 외부 사례 탐색 워크플로

## 한 문장 정의

외부 사례 탐색 워크플로는 인터넷 검색으로 잘 만들어진 AI 시스템, 저장소, 문서, 운영 패턴을 찾고, 증거 기반 후보로 평가한 뒤, 승인된 것만 이 스켈레톤에 흡수하게 만드는 운영 절차입니다.

## 무엇을 하는가

이 워크플로는 외부 자료를 출처와 경계 없이 바로 복사하거나 기능으로 추가하지 않습니다. 먼저 검색 질문을 만들고, 후보를 수집하고, 후보 카드로 정리하고, 우리 프로젝트에 맞는 적용 가능성을 평가합니다. 평가를 통과한 후보만 dry-run 제안으로 올리고, 사용자가 승인한 뒤에 실제 문서, 규칙, 스킬, 스크립트로 반영합니다.

이 워크플로의 목적은 특정 프레임워크를 도입하는 것이 아닙니다. 후보 카드는 프로세스를 검증하기 위한 예시일 수도 있고, 실제 채택 후보일 수도 있습니다. 어느 경우든 실제 반영은 승인된 dry-run 제안으로만 진행합니다.

검색 대상은 다음 네 가지로 나눕니다.

- 공개 저장소: 에이전트 프레임워크, 운영 스켈레톤, 평가 harness, 스킬 구조, 문서 구조를 찾습니다.
- 공식 문서: API, SDK, MCP, 프레임워크의 현재 권장 사용법을 확인합니다.
- 기술 글과 사례 분석: 운영 패턴, 실패 사례, 설계 판단 근거를 찾습니다.
- 기존 기준 저장소: 이미 비교 대상으로 삼은 저장소를 재검토해 누락된 패턴을 찾습니다.

## 왜 필요한가

이 프로젝트의 목표는 처음부터 모든 것을 직접 발명하는 것이 아니라, 이미 검증된 좋은 구조와 코드를 찾아 우리 운영 방식에 맞게 흡수하는 것입니다. 하지만 외부 사례를 무비판적으로 가져오면 보안, 유지보수 비용, 프로젝트 철학 불일치, 공개/재배포 시 라이선스 문제가 생깁니다. 개인용 로컬 프로젝트에서는 라이선스가 채택을 막는 주된 기준은 아니며, 외부 배포가 없는 경우 일부 코드 복사도 선택할 수 있습니다. 다만 나중에 공개하거나 다른 프로젝트로 전파될 수 있으므로 출처와 라이선스, 복사 범위, 재배포 전 재검토 조건은 계속 기록합니다.

따라서 검색 능력은 단순한 웹 접근이 아니라 판단 능력이어야 합니다. 좋은 사례를 찾는 것과 좋은 사례를 우리 시스템에 안전하게 흡수하는 것은 다른 일입니다. 이 워크플로는 그 차이를 운영 절차로 고정합니다.

## 어떻게 동작하는가

기본 흐름은 다음과 같습니다.

```text
문제 정의
  -> 검색 질문 작성
  -> 외부 후보 수집
  -> 필요 시 runtime/external-repos/에 clone
  -> 후보 카드 작성
  -> 점수화와 리스크 확인
  -> 적용 방식 결정
  -> dry-run 제안 작성
  -> 사용자 채팅 승인/거절
  -> 실제 반영
  -> 검증과 로그 기록
  -> 세션 인수인계 갱신
```

### 1. 문제 정의

먼저 찾으려는 대상을 한 문장으로 정합니다. 예를 들어 "에이전트가 외부 사례를 평가하는 기준을 개선한다"와 "스켈레톤에 검색 스크립트를 추가한다"는 다른 문제입니다. 문제 정의가 흐리면 검색 결과가 많아져도 적용할 수 없습니다.

### 2. 검색 질문 작성

검색 질문은 최소 두 종류로 나눕니다.

- 넓은 질문: 어떤 프로젝트와 패턴이 존재하는지 찾습니다.
- 좁은 질문: 특정 패턴의 구현, 라이선스, 검증 방식, 실패 사례를 확인합니다.

검색 질문에는 가능하면 도메인, 산출물, 품질 기준을 포함합니다.

```text
좋지 않음: ai agent framework
좋음: open source ai agent framework eval harness memory workflow GitHub stars recently updated
좋음: agent operating loop handoff activity log open source repository
```

### 3. 외부 후보 수집

후보는 한 번에 너무 많이 확정하지 않습니다. 기본값은 10개 이하로 수집하고, 깊게 보는 후보는 3개 이하로 제한합니다. 후보가 많아지면 평가보다 수집이 목적이 됩니다.

공개 저장소는 최소한 다음을 확인합니다.

- 최근 활동 여부
- star, fork, issue, release 같은 유지보수 신호
- 라이선스와 재배포 가능성. 개인용 내부 프로젝트에서는 차단 기준보다 기록 기준으로 보고, 코드 복사도 검토할 수 있습니다. 공개/공유 가능성이 있으면 별도 검토합니다.
- 테스트와 문서 존재 여부
- 우리 스켈레톤과 책임이 겹치는 부분

star 수는 후보를 빨리 훑기 위한 신호일 뿐 채택 여부를 결정하지 않습니다. 낮은 star라도 다음 신호가 있으면 깊게 봅니다.

- 작성자나 조직이 해당 분야에서 신뢰할 만합니다.
- 코드 구조와 모듈 경계가 작고 명확합니다.
- 테스트, 예제, 실패 처리, 문서가 실제 사용 기준으로 작성되어 있습니다.
- 최근 commit이 목적 있는 변경이고, issue/PR 대응 품질이 좋습니다.
- 특정 도메인에서는 사실상 표준이거나, 새로 나온 프로젝트라 아직 star가 낮을 뿐입니다.
- 우리 프로젝트에 dependency, wrapper, partial copy, concept-only 중 하나로 작게 흡수할 수 있는 부분이 있습니다.

공식 문서는 현재 날짜 기준으로 최신성을 확인합니다. 버전이 중요한 도구는 문서 날짜나 changelog를 같이 확인합니다.

저장소 구조를 직접 분석해야 하면 외부 repo는 `runtime/external-repos/` 아래에 clone합니다. 이 위치는 분석용 런타임 작업 공간이며, 우리 프로젝트 소스나 장기 문서가 아닙니다. 기본 경로는 `runtime/external-repos/<host>/<owner>__<repo>/`입니다.

예시:

```text
runtime/external-repos/github.com/NousResearch__hermes-agent/
runtime/external-repos/github.com/langchain-ai__langgraph/
```

clone 원본은 읽기 전용 분석 대상으로 취급합니다. 분석 결과는 후보 카드에 남기고, 적용할 내용은 dry-run 제안으로 분리합니다. clone 원본은 새 프로젝트 bootstrap 결과로 복사되지 않아야 합니다.

에이전트가 이 과정을 실행할 때는 `scripts/reference-intake.py`를 우선 사용합니다.

```powershell
# 실제 clone 전 안전 경로와 명령만 확인
python3 scripts/reference-intake.py clone --url <repo-url> --format json

# 이미 clone된 repo를 구조 분석
python3 scripts/reference-intake.py analyze --local-path runtime/external-repos/<host>/<owner>__<repo> --format json

# 후보 카드 초안 생성
python3 scripts/reference-intake.py card-draft --local-path runtime/external-repos/<host>/<owner>__<repo> --url <repo-url>
```

실제 `git clone`은 외부 네트워크와 파일 쓰기를 동반하므로 사용자 승인 후 `--apply`를 붙일 때만 실행합니다.

### 4. 후보 카드 작성

외부 사례는 먼저 후보 카드로 저장합니다. 카드가 없으면 채택할 수 없습니다.

후보 카드는 `research/reference-candidates/`에 저장합니다. 새 후보는 `research/reference-candidates/_template.md`를 복사해 `YYYY-MM-DD-<short-name>.md` 형식으로 만듭니다.

```text
name:
url:
source_type: repository | official_docs | article | paper | existing_reference
searched_for:
why_it_matters:
useful_patterns:
evidence:
local_clone_path:
checked_revision:
risks:
license:
freshness:
applies_to:
adoption_decision: adopt | adapt | copy | defer | reject
next_action:
```

후보 카드는 "좋아 보인다"가 아니라 "어떤 증거 때문에 어떤 부분을 참고하거나 복사할 수 있다"를 남깁니다. 코드나 문구를 그대로 가져와야 할 때는 라이선스, 출처, 확인한 revision, 복사할 파일 또는 함수 범위를 먼저 확인합니다.

저장소를 clone해서 분석했다면 후보 카드에 `local_clone_path`와 확인한 commit, tag, branch 중 하나를 기록합니다. clone하지 않고 웹 문서나 공식 문서만 본 경우에는 `local_clone_path`에 `not cloned`라고 적습니다.

### 5. 점수화와 리스크 확인

후보는 100점 만점으로 평가합니다.

| 기준 | 배점 | 확인 내용 |
| --- | ---: | --- |
| 문제 적합성 | 20 | 지금 해결하려는 문제와 직접 연결되는가 |
| 구조 명확성 | 15 | 책임 경계와 실행 흐름이 이해 가능한가 |
| 검증 가능성 | 15 | 테스트, eval, 운영 로그, 재현 절차가 있는가 |
| 유지보수 신호 | 15 | 최근 활동, 이슈 관리, 문서 업데이트가 있는가 |
| 흡수 비용 | 15 | 우리 스켈레톤에 작게 번역할 수 있는가 |
| 보안/재배포 리스크 | 10 | 민감 정보, 위험한 자동화, 공개/재배포 시 라이선스 문제가 없는가 |
| 설명 가치 | 10 | 사용자가 판단할 수 있는 근거를 제공하는가 |

점수가 낮아도 배울 점이 있으면 `defer`로 둘 수 있습니다. 다만 `adopt`, `adapt`, `copy`는 적용 위치와 검증 방법이 있어야 합니다.

### 6. 적용 방식 결정

결정은 다섯 가지 중 하나입니다.

- `adopt`: 구조나 절차를 거의 그대로 채택합니다. 공식 문서나 단순 규칙에만 제한적으로 사용합니다.
- `adapt`: 핵심 패턴만 우리 운영 방식에 맞게 번역합니다. 기본값입니다.
- `copy`: 코드나 구조 일부를 실제 파일로 복사합니다. 개인 로컬 사용과 같이 외부 배포가 없고, 출처와 라이선스와 복사 범위가 기록됐을 때만 사용합니다.
- `defer`: 유용하지만 현재 목표와 검증 방법이 부족해 보류합니다.
- `reject`: 가치보다 리스크나 비용이 큽니다.

이 프로젝트에서는 `adapt`를 기본값으로 둡니다. 외부 저장소의 구조를 통째로 복사하지 않고, 작동 원리를 우리 문서, 규칙, 스킬, 스크립트 중 맞는 위치로 옮깁니다. 다만 사용자가 개인 로컬 사용과 외부 배포 없음 조건을 명확히 하면 `copy`와 `partial_copy`를 승인 가능한 경로로 둡니다.

적용 방식 결정 후에는 모듈형 흡수 방식을 따로 고릅니다.

- `dependency`: 패키지나 도구를 그대로 설치해 사용합니다.
- `wrapper`: 외부 CLI, API, 모듈 일부를 얇은 adapter로 감싸 사용합니다.
- `partial_copy`: 일부 코드나 구조를 가져옵니다. 개인 로컬 프로젝트에서는 라이선스가 차단 기준은 아니지만, 출처와 license, 확인한 revision, 복사 범위, 재배포 전 재검토 조건을 남깁니다.
- `concept_only`: 코드 없이 구조, 운영 원칙, 실패 처리 방식만 번역합니다.
- `direct_implementation`: 직접 구현합니다. 이 선택은 "쓸 만한 오픈소스가 없거나, 맞지 않거나, 너무 무겁다"는 이유가 있어야 합니다.

### 7. dry-run 제안 작성

채택 또는 수정 채택 후보는 바로 반영하지 않고 dry-run 제안으로 만듭니다. 제안에는 다음이 있어야 합니다.

- 바꿀 파일이나 만들 파일
- 반영할 외부 패턴
- 그대로 가져오지 않고 바꾸는 부분
- dependency, wrapper, partial copy, concept-only, direct implementation 중 어떤 흡수 방식을 택하는지
- partial copy를 선택한다면 복사할 파일/함수/스니펫 범위, 원본 라이선스, 원본 revision, 로컬 전용 조건, 재배포 전 재검토 조건
- 직접 구현한다면 왜 기존 오픈소스를 쓰지 않는지
- 검증 방법
- 롤백 또는 중단 기준
- 사용자 승인 필요 여부

dry-run 제안은 `runtime/proposals/reference-adoption/`에 저장합니다. 제안은 실제 적용이 아니며, 승인 전에는 장기 운영 문서나 규칙을 바꾸지 않습니다.

예시 후보로 만든 제안서는 제목과 본문에 "예시" 성격을 분명히 표시합니다. 특정 저장소나 프레임워크 이름이 제안서에 들어가더라도, 그 자체가 도입 계획이라는 뜻은 아닙니다.

승인 전에는 장기 운영 규칙, 공통 스킬, 검증 스크립트를 실제로 바꾸지 않습니다.

### 8. 채팅 승인/거절 처리

사용자는 제안서 파일을 직접 수정하지 않습니다. 채팅에서 승인, 거절, 보류 의사를 밝히면 에이전트가 다음을 수행합니다.

- 승인: 제안서의 결정 기록을 갱신하고, 승인된 범위 안에서 실제 파일을 수정하고, 검증을 실행하고, 후보 카드와 활동 로그와 세션 인수인계를 갱신합니다.
- 거절: 제안서 상태를 `rejected`로 바꾸고, 후보 카드의 최종 기록과 활동 로그에 거절 이유를 남깁니다.
- 보류: 제안서 상태를 `deferred`로 바꾸고, 다시 볼 조건을 기록합니다.

승인/거절/보류의 출처는 채팅입니다. 에이전트는 사용자의 의사를 파일에 반영하는 실행자이며, 사용자에게 문서 편집을 요구하지 않습니다.

### 9. 실제 반영과 검증

승인된 제안만 구현합니다. 반영 후에는 변경 범위에 맞는 검증을 실행합니다.

- 문서나 규칙 변경: `python3 scripts/verify-skeleton.py`
- 후보 카드 변경: `python3 scripts/validate-reference-candidates.py`
- dry-run 제안 변경: `python3 scripts/validate-reference-proposals.py`
- 검색/평가 스크립트 추가: 스크립트 `--help`, 단위 테스트, dry-run 실행
- 스킬 추가: 활성 조건, 실패 신호, 관련 문서 포인터 확인
- Notion 동기화 포함: 중복 방지 프로토콜과 fetch 검증

검증을 실행하지 못하면 이유를 활동 로그와 최종 응답에 남깁니다.

## 결과는 무엇인가

이 워크플로가 적용되면 외부 검색 결과는 다음 상태 중 하나로 정리됩니다.

- 후보 카드로 남아 재검토할 수 있습니다.
- dry-run 제안으로 승격되어 승인 대기합니다.
- 승인 후 문서, 규칙, 스킬, 스크립트로 반영됩니다.
- 리스크 때문에 보류 또는 폐기됩니다.

결과적으로 프로젝트는 외부 사례를 빠르게 참고하되, 출처와 판단 근거 없이 구조가 불어나는 일을 피합니다.

## 실패 신호

다음 상황이 보이면 워크플로를 중단하고 문제 정의로 돌아갑니다.

- 검색 결과 URL만 많고 후보 카드가 없습니다.
- star 수나 유명도만 보고 채택하려 합니다.
- 보안 리스크를 확인하지 않았고, 코드 복사 또는 공개/재배포 가능성이 있는데 라이선스와 출처를 기록하지 않았습니다.
- 적용 위치가 문서인지, 규칙인지, 스킬인지, 스크립트인지 불명확합니다.
- 흡수 방식이 dependency인지, wrapper인지, partial copy인지, concept-only인지, direct implementation인지 불명확합니다.
- 검증 방법 없이 "좋아 보이는 구조"를 추가하려 합니다.
- 외부 저장소의 책임 구조를 이해하지 못한 채 파일 구조만 복사합니다.
- 개인 로컬 사용 조건으로 복사했는데 나중에 공개/공유할 때 라이선스 재검토를 하지 않습니다.

## 기능 추가/수정 판단 기준

이 워크플로를 수정할 때는 다음 기준을 사용합니다.

- 검색 대상이나 평가 기준이 반복적으로 부족하면 수정합니다.
- 후보 카드 없이 바로 구현되는 일이 반복되면 스킬이나 검증 스크립트로 승격합니다.
- 검색 API 연동이 자주 필요해지면 별도 스크립트나 MCP 도구 후보로 검토합니다.
- 특정 도메인 후보가 반복되면 도메인별 평가 기준을 추가합니다.
- 결과가 너무 무거워지면 후보 수, 깊은 검토 수, 필수 필드를 줄입니다.

새 자동화를 추가하려면 먼저 dry-run으로 동작해야 합니다. 자동화가 장기 문서나 공통 규칙을 직접 수정하려면 사용자 승인과 검증 로그가 필요합니다.

## 구현 연결 정보

- 기능 결정 가이드: `docs/FEATURE_DECISION_GUIDE.md`
- 워크플로 카탈로그: `docs/WORKFLOW_CATALOG.md`
- 문서화 스타일 가이드: `docs/DOCUMENTATION_STYLE_GUIDE.md`
- 후보 카드 디렉터리: `research/reference-candidates/`
- 후보 카드 템플릿: `research/reference-candidates/_template.md`
- 외부 저장소 clone 작업 공간: `runtime/external-repos/`
- 외부 사례 적용 제안 초안 생성: `scripts/create-reference-proposal.py`
- 외부 사례 적용 제안: `runtime/proposals/reference-adoption/`
- 외부 사례 적용 제안 검증: `scripts/validate-reference-proposals.py`
- 런타임 이벤트 스키마: `docs/RUNTIME_EVENT_SCHEMA.md`
- 세션 연속성 규칙: `docs/SESSION_CONTINUITY.md`
- 스켈레톤 검증: `scripts/verify-skeleton.py`
- 활동 로그: `runtime/activity-log.jsonl`

## 에이전트 책임: partial copy 기록

사용자는 후보 카드, 제안서, copied-source ledger를 직접 편집하거나 실행하지 않습니다. 사용자가 채팅에서 `copy` 또는 `partial_copy` 방향을 승인하면 에이전트가 다음 기록을 같은 작업 단위 안에서 완료합니다.

- 후보 카드: `adoption_decision: copy`, `what_to_copy_directly`, `copy_boundary`
- 제안서: `absorption_mode: partial_copy`, `copy_boundary`, 실제 변경 범위
- 장부: `python3 scripts/reference-copy-ledger.py add ...`로 `runtime/reference-copy-ledger.jsonl` append
- 검증: `python3 scripts/reference-copy-ledger.py check`, `python3 scripts/security-scan.py --strict`
- 마감 기록: `runtime/activity-log.jsonl`, `runtime/state/session-handoff.md`

partial copy가 실제 파일 수정으로 이어졌는데 장부 기록이 없다면 작업은 완료로 보지 않습니다.
