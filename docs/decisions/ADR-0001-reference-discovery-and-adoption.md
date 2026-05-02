# ADR-0001: 외부 사례 탐색과 도입은 후보 카드와 dry-run 제안을 거친다

## 상태

accepted

## 날짜

2026-04-27

## 맥락

이 스켈레톤의 중요한 목적은 처음부터 모든 것을 직접 설계하지 않고, 이미 잘 만들어진 외부 사례를 찾아 우리 프로젝트에 맞게 흡수하는 것입니다. 하지만 외부 저장소나 프레임워크를 바로 가져오면 다음 문제가 생깁니다.

- 유명한 도구를 곧바로 도입하려는 것처럼 보일 수 있습니다.
- 라이선스, 보안, 유지보수 리스크를 놓칠 수 있습니다.
- 우리 스켈레톤의 단순한 운영 철학보다 외부 구조가 앞설 수 있습니다.
- 사용자 승인 없이 장기 운영 문서가 바뀔 수 있습니다.

## 결정

외부 사례는 출처와 경계 없이 바로 적용하지 않습니다. 반드시 다음 단계를 거칩니다.

```text
외부 사례 탐색
  -> 후보 카드 작성
  -> 후보 카드 검증
  -> dry-run 제안 작성
  -> 제안 검증
  -> 사용자의 채팅 승인 또는 거절
  -> 에이전트가 실제 반영/보류 기록 처리
```

사용자는 문서를 직접 수정하지 않습니다. 사용자가 채팅으로 승인, 거절, 보류 의사를 밝히면 에이전트가 제안서, 후보 카드, 활동 로그, 세션 인수인계를 갱신합니다.

개인 로컬 사용처럼 외부 배포가 없는 작업에서는 일부 코드 복사를 금지하지 않습니다. 후보 카드의 `adoption_decision: copy`와 제안서의 `absorption_mode: partial_copy`를 사용하고, 출처, 라이선스, 확인한 revision, 복사 범위, 재배포 전 재검토 조건을 기록한 뒤 승인된 범위만 반영합니다.

## 대안

- 외부 사례를 바로 문서나 코드에 반영한다.
- 검색 결과를 채팅 요약으로만 남긴다.
- 후보 카드만 만들고 dry-run 제안은 생략한다.
- 모든 과정을 자동화해 주기적으로 적용한다.

## 근거

후보 카드는 외부 사례 자체를 평가하는 데 적합하고, dry-run 제안은 그 사례를 우리 스켈레톤에 어떻게 번역할지 검토하는 데 적합합니다. 두 단계를 분리하면 "좋아 보이는 도구"와 "우리 프로젝트에 실제로 필요한 변경"을 구분할 수 있습니다.

사용자 승인도 파일 수정이 아니라 채팅 의사 표현으로 처리해야 합니다. 이 프로젝트의 운영 목표는 사용자가 직접 문서 구조를 관리하는 것이 아니라, 에이전트가 승인된 변경을 책임지고 반영하는 것입니다.

## 결과

- 외부 사례 도입은 추적 가능한 절차가 됩니다.
- 특정 프레임워크 이름이 등장해도 도입 계획으로 오해되지 않습니다.
- 승인 전에는 장기 운영 문서나 규칙이 바뀌지 않습니다.
- 개인 로컬 사용에서는 코드 복사도 추적 가능한 채택 방식이 됩니다.
- 제안이 승인/거절/보류되면 에이전트가 관련 파일과 로그를 갱신합니다.

## 영향 범위

- `docs/REFERENCE_DISCOVERY_WORKFLOW.md`
- `research/reference-candidates/`
- `runtime/proposals/reference-adoption/`
- `scripts/validate-reference-candidates.py`
- `scripts/validate-reference-proposals.py`
- `scripts/create-reference-proposal.py`
- `runtime/activity-log.jsonl`
- `runtime/state/session-handoff.md`

## 검증

이 결정과 관련된 변경 후에는 다음을 실행합니다.

```powershell
python3 scripts/verify-skeleton.py
python3 scripts/validate-reference-candidates.py
python3 scripts/validate-reference-proposals.py
python3 scripts/list-open-questions.py --count
```

## 추가 결정: 장부 기록 주체

copied-source ledger는 사용자가 수동으로 남기는 체크리스트가 아닙니다. 오픈소스 코드를 실제 파일로 복사하는 에이전트가 같은 작업 안에서 `scripts/reference-copy-ledger.py add`를 실행하고, 후보 카드·제안서·활동 로그·세션 인수인계를 함께 갱신합니다. 사용자의 역할은 채팅에서 승인, 거절, 보류, 방향 수정을 말하는 것까지입니다.
