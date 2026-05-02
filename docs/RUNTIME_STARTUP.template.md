# Runtime Startup

## 한 문장 정의

이 문서는 프로젝트를 실제로 실행하고, 정상 구동 여부를 확인하고, 실패했을 때 어디를 볼지 정리하는 실행 계약입니다.

## 무엇을 하는가

프로젝트가 문서상으로만 완성된 상태에 머무르지 않도록 실행 명령, 환경 변수, 포트, healthcheck, 첫 검증 명령, 실패 로그 위치를 한곳에 둡니다. 에이전트는 "실행 가능하다"와 "실제로 실행해 확인했다"를 구분해서 기록합니다.

## 왜 필요한가

새 프로젝트는 목표와 문서가 있어도 실행 계약이 없으면 매번 구동 방법을 다시 추측하게 됩니다. 이 문서는 새 세션이나 다른 에이전트가 프로젝트를 이어받아도 바로 실행하고 확인할 수 있게 만드는 최소 runbook입니다.

## 사용 시점

- 새 프로젝트의 첫 실행 전
- 포트, env, Docker, 서비스 구성이 바뀔 때
- "실제로 돌아가나?"를 확인해야 할 때
- 배포나 데모 전에 healthcheck를 고정해야 할 때

## 실행 환경

- `runtime_environment`:
- `language_or_framework`:
- `package_manager`:
- `requires_docker`: yes / no
- `requires_network`: yes / no

## 환경 변수

| 이름 | 필수 여부 | 예시 또는 위치 | 설명 |
| --- | --- | --- | --- |
|  | required / optional | `.env.example` |  |

민감 값은 원문으로 기록하지 않습니다. 예시는 `.env.example` 또는 placeholder로 둡니다.

## 실행 명령

```powershell
# install

# start

# stop
```

## 포트와 엔드포인트

| 서비스 | 포트 | URL | 설명 |
| --- | ---: | --- | --- |
|  |  | `http://localhost:<port>` |  |

## Healthcheck

```powershell
# 가장 싼 정상 확인 명령
```

성공 기준:

- 

## 첫 검증 명령

```powershell
# unit / smoke / integration 중 가장 싼 검증부터
```

## 실패 시 확인할 것

- 프로세스가 떠 있는가:
- 포트 충돌이 있는가:
- env 누락이 있는가:
- 로그 위치:
- 캐시/빌드 산출물 정리 기준:

## 성공 상태

- 실행 명령이 최신입니다.
- 필수 env와 포트가 문서화되어 있습니다.
- healthcheck가 실제 성공/실패를 구분합니다.
- 마지막 검증 결과가 활동 로그나 세션 인수인계에 남아 있습니다.

## 실패 신호

- "될 것"이라고만 쓰고 실제 실행 명령이 없습니다.
- 포트나 env가 README, Docker, 코드와 다릅니다.
- healthcheck가 없거나 항상 성공합니다.
- 실패 로그 위치가 없습니다.

## 구현 연결 정보

- 프로젝트 프로필: `docs/PROJECT_PROFILE.md`
- 운영 루프: `docs/OPERATING_LOOP.md`
- 런타임 이벤트 스키마: `docs/RUNTIME_EVENT_SCHEMA.md`
- 세션 인수인계: `runtime/state/session-handoff.md`
- 활동 로그: `runtime/activity-log.jsonl`
