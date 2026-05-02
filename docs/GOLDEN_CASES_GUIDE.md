# Golden Cases 작성 가이드

## 한 문장 정의

Golden Cases는 skill이나 반복 절차를 바꾼 뒤 “정말 좋아졌는지” 확인하기 위한 작은 회귀 평가셋입니다.

## 무엇을 하는가

각 skill 아래 `goldens/*.yaml` 파일을 두고, 입력과 기대 속성, 금지 패턴, 평가 방식을 기록합니다. `scripts/eval.py <skill-name>`은 해당 골든 케이스를 읽어 로컬에서 가능한 평가는 즉시 실행하고, 아직 연결되지 않은 LLM judge 평가는 skip으로 보고합니다.

## 왜 필요한가

자가 개선은 기록만으로는 개선인지 알 수 없습니다. 실패 패턴을 skill로 승격할 때, 기존에 잘 되던 케이스가 깨지면 장기 기억이 오히려 회귀가 됩니다. Golden Cases는 “이 상황에서는 최소한 이런 속성을 가져야 한다”는 작고 반복 가능한 기준을 제공합니다.

## 시작 규모

- skill당 1~3개부터 시작합니다.
- 0개도 허용하지만 그 skill은 회귀 검증 범위 밖이며 `regression_uncovered`로 보고됩니다.
- 운영 중 실제 실패가 생기면 그 실패를 가장 먼저 골든 케이스로 바꿉니다.
- 너무 넓은 정답 문장보다 출력의 의미 속성과 금지 패턴을 적습니다.

## 파일 위치

```text
skills/active/<skill-name>/goldens/case-001.yaml
skills/_candidates/<skill-name>/goldens/case-001.yaml
skills/_meta/<skill-name>/goldens/case-001.yaml
```

템플릿은 `skills/_templates/GOLDEN.template.yaml`입니다.

## 필드 기준

```yaml
id: case-001
skill: <skill-name>
created_at: <YYYY-MM-DD>
last_verified_at: <YYYY-MM-DD>
staleness_check_due: <YYYY-MM-DD>

input: |
  <사용자 입력 또는 트리거 컨텍스트>

expected_properties:
  - <출력에 반드시 포함되어야 할 의미 속성>

forbidden_patterns:
  - <출력에 있으면 안 되는 패턴>

evaluation:
  judge_method: "schema-check"
  pass_threshold: 0.8
```

## 평가 방식

- `schema-check`: 현재 로컬 구현에서 즉시 실행됩니다. `input` 또는 `actual_output`에 `expected_properties`가 포함되고 `forbidden_patterns`가 없으면 통과합니다.
- `heuristic`: v1에서는 `schema-check`와 같은 로컬 의미로 처리합니다. 더 정교한 휴리스틱이 필요하면 별도 스크립트로 확장합니다.
- `llm-as-judge`: v1에서는 발견만 하고 skip으로 보고합니다. evaluator 역할 호출이 연결된 뒤 활성 평가로 승격합니다.

## 운영 흐름

1. skill 변경 또는 새 skill 후보가 생기면 골든 케이스가 있는지 확인합니다.
2. 골든 케이스가 있으면 `scripts/eval.py <skill-name>`으로 회귀를 확인합니다.
3. 실패하면 코드와 골든 중 무엇이 outdated인지 자동 결정하지 않고 사용자 승인 대상으로 올립니다.
4. 통과 결과와 실패 결과는 `state/progress.md`, `state/failures.jsonl`, 또는 completion evidence에 연결합니다.

## 갱신 기준

- `staleness_check_due`가 지난 케이스는 stale 후보입니다.
- 라이브러리 메이저 업데이트나 정책 변경으로 정답 속성이 바뀌면 기존 케이스를 조용히 덮어쓰지 않고 새 케이스를 추가하거나 deprecate 근거를 남깁니다.
- 생성형 답변의 표현 차이 때문에 깨지는 케이스는 expected_properties를 의미 단위로 완화합니다.

## 절대 하지 말 것

- 골든이 깨졌을 때 코드나 골든 중 하나를 자동으로 고르지 않습니다.
- 특정 문장 전체를 정답으로 강제해 우연한 실패를 만들지 않습니다.
- 두 전문가가 의견이 갈릴 정도로 모호한 케이스를 회귀 기준으로 쓰지 않습니다.
- 골든 케이스 없이 active 승격을 “검증 완료”로 표현하지 않습니다.

## 구현 연결 정보

- 평가 스크립트: `scripts/eval.py`
- 골든 템플릿: `skills/_templates/GOLDEN.template.yaml`
- skill 생명주기: `docs/SKILL_DISTRIBUTION_MODEL.md`
- verify 게이트: `scripts/verify.py`
