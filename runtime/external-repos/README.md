# External Repository Clones

## 한 문장 정의

이 디렉터리는 외부 오픈소스 저장소를 분석하기 위해 clone하는 런타임 작업 공간입니다.

## 무엇을 하는가

비슷한 서비스를 하는 오픈소스를 찾았을 때, 저장소 원본은 이곳에 clone합니다. clone한 저장소는 우리 프로젝트의 소스가 아니라 읽기 전용 분석 대상입니다. 분석 결과는 후보 카드와 dry-run 제안으로 따로 남깁니다.

기본 경로 형식은 다음과 같습니다.

```text
runtime/external-repos/
  github.com/
    <owner>__<repo>/
```

예시는 다음과 같습니다.

```text
runtime/external-repos/github.com/NousResearch__hermes-agent/
runtime/external-repos/github.com/langchain-ai__langgraph/
```

## 왜 필요한가

외부 저장소를 프로젝트 루트나 `research/` 아래에 직접 clone하면 원본 코드와 우리 판단 기록이 섞입니다. 그러면 새 프로젝트로 복사될 위험이 생기고, 에이전트가 외부 코드를 우리 코드처럼 착각할 수 있습니다.

따라서 clone 원본은 `runtime/`에 두고, 오래 남길 판단 결과만 `research/reference-candidates/`와 `runtime/proposals/reference-adoption/`에 둡니다.

## 어떻게 동작하는가

1. 외부 후보를 찾습니다.
2. 저장소 분석이 필요하면 이 디렉터리 아래에 clone합니다.
3. clone 직후 후보 카드에 `local_clone_path`와 확인한 commit, tag, branch를 기록합니다.
4. 저장소 구조, 라이선스, 문서, 테스트, 운영 패턴을 읽습니다.
5. 분석 결과는 후보 카드에 요약합니다.
6. 실제 적용 가능성이 있으면 dry-run 제안을 만듭니다.
7. 사용자가 채팅으로 승인하기 전에는 우리 문서, 규칙, 스킬, 스크립트에 반영하지 않습니다.

## 운영 규칙

- clone 원본은 읽기 전용 분석 대상으로 취급합니다.
- 외부 repo 안에서 실험을 하더라도 그 결과를 우리 프로젝트 코드로 바로 복사하지 않습니다.
- 외부 repo의 `.env`, 키, 토큰, 샘플 secret, 생성물은 후보 카드나 로그에 원문으로 남기지 않습니다.
- 코드나 문구를 가져와야 하면 라이선스와 출처를 후보 카드에 먼저 기록합니다.
- 분석이 끝나면 clone 원본은 삭제해도 됩니다. 남겨야 하는 것은 후보 카드와 제안서입니다.
- 새 프로젝트 bootstrap은 이 디렉터리의 clone 원본을 복사하지 않습니다.

## 결과는 무엇인가

이 규칙을 지키면 외부 repo 원본, 분석 기록, 실제 적용 제안이 분리됩니다.

- 원본 clone: `runtime/external-repos/`
- 판단 기록: `research/reference-candidates/`
- 적용 제안: `runtime/proposals/reference-adoption/`

## 실패 신호

- 외부 repo가 프로젝트 루트, `src/`, `docs/`, `research/`에 clone되어 있습니다.
- clone한 repo의 파일을 그대로 우리 운영 문서나 스크립트로 옮겼습니다.
- 후보 카드에 clone 경로와 확인한 revision이 없습니다.
- 외부 repo 원본이 새 프로젝트 bootstrap 결과에 복사됩니다.

## 구현 연결 정보

- 외부 사례 탐색 워크플로: `docs/REFERENCE_DISCOVERY_WORKFLOW.md`
- 후보 카드 위치: `research/reference-candidates/`
- dry-run 제안 위치: `runtime/proposals/reference-adoption/`
- bootstrap 제외 규칙: `scripts/bootstrap/new-project.py`
- 임시 파일 규칙: `rules/common/ephemeral-files.md`
