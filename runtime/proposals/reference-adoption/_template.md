# <후보 이름> 기반 <제안 주제> 제안

## 상태

- `status`: proposed | accepted | rejected | applied | deferred
- `created_at`:
- `candidate_card`:
- `proposal_type`: reference_adoption_dry_run
- `approval_required`: yes | no
- `decision_source`:

## 한 문장 정의

<외부 후보에서 어떤 개념을 가져와 우리 스켈레톤에 어떤 작은 변경으로 번역할지 한 문장으로 씁니다.>

## 근거

<현재 스켈레톤의 어떤 문제가 있고, 후보 카드의 어떤 증거가 이 문제 해결에 도움이 되는지 씁니다.>

## 적용하지 않을 것

- 

## 모듈형 흡수 판단

- `absorption_mode`: dependency | wrapper | partial_copy | concept_only | direct_implementation | mixed
- `recommended_mode`:
- `reuse_boundary`:
- `direct_implementation_reason`:
- `copy_boundary`: not applicable | private local only; record source, license, revision, copied files/functions, and review again before redistribution

다음 질문에 답합니다.

- 이 후보를 의존성으로 그대로 쓸 수 있는가?
- 특정 모듈이나 CLI를 wrapper로 감싸 쓸 수 있는가?
- 일부 코드나 구조를 가져올 수 있는가? 개인 로컬 사용이라면 어떤 파일/함수/스니펫을 어디까지 복사할 것인가?
- 코드가 아니라 개념만 번역해야 하는가?
- 직접 구현한다면 왜 직접 구현해야 하는가?

## 제안 변경

### 1. <변경 영역>

대상: `<path>`

추가할 내용:

- 

예상 문구 방향:

```text
<승인 후 실제 문서에 들어갈 수 있는 문구 방향>
```

## 기대 효과

- 

## 위험

- 

완화:

- 

## 검증 계획

승인 후 실제 반영 작업에서는 다음을 실행합니다.

```powershell
python scripts/verify-skeleton.py
python scripts/validate-reference-candidates.py
python scripts/validate-reference-proposals.py
python scripts/list-open-questions.py --count
```

## 롤백 또는 중단 조건

- 

## 승인 후 실제 변경 범위

- 

## 최종 결정 기록

- `decision`: pending | accepted | rejected | applied | deferred
- `decided_at`:
- `decided_by`:
- `decision_source`:
- `applied_in`:
- `validation_result`:
