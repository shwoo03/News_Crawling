# Reference Review

## 한 문장 정의

이 문서는 새 프로젝트나 큰 기능을 시작하기 전에 참고한 오픈소스, 공식 문서, 경쟁 제품, 기존 시스템을 비교하고 어떤 부분을 채택, 수정 채택, 코드 복사, 보류, 거절할지 결정하는 검토 기록입니다.

## 무엇을 하는가

구현 전에 이미 잘 만들어진 사례를 먼저 확인합니다. 후보는 `research/reference-candidates/`에 카드로 남기고, 실제 반영이 필요하면 `runtime/proposals/reference-adoption/`의 dry-run 제안으로 승격합니다. 이 문서는 후보 카드 전체를 반복하지 않고, 프로젝트 관점의 최종 판단만 요약합니다.

## 왜 필요한가

AI 에이전트는 목표를 받으면 빠르게 직접 구현하려는 경향이 있습니다. 하지만 이미 좋은 오픈소스나 참고 시스템이 있다면 처음부터 만들기보다 dependency, wrapper, partial copy, concept-only 중 어떤 방식으로 흡수할지 먼저 판단해야 합니다. 개인 로컬 사용처럼 외부 배포가 없는 작업에서는 라이선스가 자동 차단 사유가 아니므로, 출처와 라이선스와 복사 범위를 기록한 `partial_copy`도 선택지입니다.

## 사용 시점

- 새 프로젝트를 처음 구축하기 전
- 큰 기능을 새로 만들기 전
- 사용자가 참고 링크나 경쟁 제품을 제공했을 때
- 구현 방향이 막혔고 외부 사례 비교가 필요한 때

## 검토 대상

| 이름 | 유형 | 링크 | 후보 카드 | 현재 결정 |
| --- | --- | --- | --- | --- |
|  | repository / official_docs / product / paper / article |  | `research/reference-candidates/<file>.md` | adopt / adapt / copy / defer / reject |

## 모듈형 흡수 판단

| 이름 | 흡수 방식 | 경계 | 직접 구현 여부 |
| --- | --- | --- | --- |
|  | dependency / wrapper / partial_copy / concept_only / direct_implementation / mixed | 어떤 부분까지만 가져오는가 | 직접 구현한다면 이유 |

## 채택한 것

- 

## 수정 채택한 것

- 

## 코드 복사한 것

- 

## 보류한 것

- 

## 거절한 것

- 

## 성공 상태

- 최소 3개 이하의 깊은 후보가 카드로 정리되었습니다.
- 각 후보에 흡수 방식이 정해졌습니다.
- 코드 복사 후보는 로컬 전용 조건, 출처, 라이선스, revision, 복사 범위가 정리되었습니다.
- 직접 구현하는 부분은 왜 직접 구현하는지 설명되어 있습니다.
- 실제 반영 전 dry-run 제안과 검증 방법이 연결되어 있습니다.

## 실패 신호

- URL 목록만 있고 후보 카드가 없습니다.
- star 수나 유명도만 보고 결정했습니다.
- 어떤 부분을 가져오고 어떤 부분을 버릴지 경계가 없습니다.
- 직접 구현하면서 기존 오픈소스를 쓰지 않는 이유가 없습니다.
- 코드 복사 또는 공개/재배포 가능성이 있는데 출처와 라이선스를 기록하지 않았습니다.

## 구현 연결 정보

- 외부 사례 탐색 워크플로: `docs/REFERENCE_DISCOVERY_WORKFLOW.md`
- 후보 카드 위치: `research/reference-candidates/`
- 후보 카드 템플릿: `research/reference-candidates/_template.md`
- 적용 제안 위치: `runtime/proposals/reference-adoption/`
- 적용 제안 템플릿: `runtime/proposals/reference-adoption/_template.md`
- 후보 카드 검증: `python3 scripts/validate-reference-candidates.py`
- 적용 제안 검증: `python3 scripts/validate-reference-proposals.py`
