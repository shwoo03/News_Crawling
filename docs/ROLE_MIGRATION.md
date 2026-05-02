# 역할 전환 가이드

## 한 문장 정의

역할 전환 가이드는 v1의 Codex 중심 운영을 유지할지, v2에서 planner 같은 일부 역할을 Claude 또는 다른 실행자로 옮길지 판단하고 바꾸는 절차입니다.

## 무엇을 하는가

이 문서는 모델 이름을 문서와 스크립트에 흩뿌리지 않고 `config/roles.yaml` 한 곳에서 역할별 실행자를 바꾸게 합니다. 전환 대상은 에이전트 이름이 아니라 역할입니다. 기본 역할은 planner, implementer, researcher, verifier, evaluator, escalation입니다.

## 왜 필요한가

Codex와 Claude는 장점과 호출 방식이 다릅니다. 프로젝트가 커지면 큰 방향을 잡는 역할과 구현·검증 역할을 분리하고 싶어질 수 있습니다. 전환 기준이 없으면 특정 모델명에 맞춘 문서와 스크립트가 늘어나고, 다음 프로젝트로 복사할 때 다시 손봐야 합니다.

## 전환 전 점검

다음 신호를 확인합니다.

- v1 운영을 충분히 반복했고 같은 task에서 재계획 3회 초과가 자주 발생합니다.
- 큰 방향 결정이 자주 번복되어 planner 역할을 분리할 가치가 있습니다.
- 구현은 안정적이지만 초기 plan 품질이나 tradeoff 정리가 부족합니다.
- verify, eval, reference refresh 같은 하위 역할은 현재 실행자로도 충분히 저렴하고 안정적입니다.

위 신호가 약하면 v1을 유지합니다. 역할 전환은 성능 개선 실험이지 기본 목표가 아닙니다.

## 전환 절차

1. `state/decisions.md`에 전환 이유와 기대 효과를 append합니다.
2. `config/roles.yaml`의 `mode`와 전환할 role의 `primary`, `model`, `fallback`만 수정합니다.
3. `AGENTS.md`의 역할 매트릭스가 사람용 요약과 맞는지 확인합니다.
4. `scripts/verify.py`를 실행해 check, lint, unit, smoke, integration을 통과시킵니다.
5. 첫 v2 작업은 작은 plan으로 시작하고, 결과를 `runtime/activity-log.jsonl`과 `state/progress.md`에 남깁니다.

## 예시 설정

아래는 예시입니다. 실제 모델명은 사용 가능한 최신 모델과 프로젝트 예산에 맞게 설정합니다.

```yaml
mode: "claude-primary"

roles:
  planner:
    primary: claude
    model: "{{사용자_설정_필요}}"
    fallback: codex

  implementer:
    primary: codex
    model: "{{사용자_설정_필요}}"

  researcher:
    primary: codex
    mode: subagent
    model: "{{사용자_설정_필요}}"

  verifier:
    primary: codex
    mode: headless
    model: "{{가벼운_모델_권장}}"

  evaluator:
    primary: codex
    mode: headless
    model: "{{가벼운_모델_권장}}"

escalation:
  trigger: "replan_count >= 3"
  to:
    primary: human
```

## 성공 기준

- 전환 후에도 `scripts/verify.py`가 통과합니다.
- 같은 task에서 재계획 3회 초과 빈도가 줄어듭니다.
- plan이 더 명확해졌다는 근거가 `state/decisions.md`나 completion evidence에 남습니다.
- 역할 전환 때문에 `.codex/`, `.claude/` generated artifact를 직접 수정하지 않습니다.

## 롤백 기준

- plan은 길어졌지만 검증 가능한 행동이 줄어듭니다.
- 구현자가 역할 설정을 이해하지 못해 실행이 느려집니다.
- 비용이나 지연 시간이 `config/policy.yaml`의 예산 기준을 자주 압박합니다.
- 같은 문제를 v1보다 더 자주 재계획합니다.

롤백은 `config/roles.yaml`을 이전 role mapping으로 되돌리고, 이유를 `state/decisions.md`에 새 항목으로 남깁니다.

## 구현 연결 정보

- 역할 설정: `config/roles.yaml`
- 정책 임계값: `config/policy.yaml`
- 운영 루프: `docs/OPERATING_LOOP.md`
- 세션 연속성: `docs/SESSION_CONTINUITY.md`
- 검증 게이트: `scripts/verify.py`
