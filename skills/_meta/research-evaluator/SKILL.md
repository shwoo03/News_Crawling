---
name: research-evaluator
description: 외부 라이브러리·오픈소스를 도입할 때 10개 후보 → 필터 → 정밀 검토 → 사용자 컨펌 절차를 따르는 스킬.
trigger:
  - "라이브러리 검색"
  - "외부 코드 도입"
  - "비슷한 오픈소스 찾기"
---

# Research Evaluator

## 절차 (config/policy.yaml의 research 섹션을 따름)

### Step 1: 후보 10개 수집
검색으로 메타데이터만 추출:
- 이름, 저장소 URL
- star 수
- 마지막 커밋 SHA + 날짜
- 라이센스
- 다운로드 수 (npm/PyPI)

### Step 2: 필터
다음 조건 모두 만족하는 것만 통과:
- 마지막 커밋 6개월 이내
- npm audit 또는 pip-audit 통과
- archived 상태 아님

### Step 3: 상위 3개 정밀 검토
- README 1회 읽기
- 최근 30일 이슈 응답률
- 코드 구조 (모듈성, 테스트 유무)

### Step 4: 채택 근거 표 작성
필수 필드 (검증 가능한 증거):
- name, repo_url
- last_commit_sha (실제 SHA)
- last_commit_date
- stars
- audit 결과 (원문 첨부)
- decision: adopt / refactor / reject
- rationale: 한 줄 이유

### Step 5: 사용자 컨펌
표를 사용자에게 제시. 사용자가 "OK" 해야 다음으로 진행.

### Step 6: 도입
- adopt: manifest.yaml에 직접 등록
- refactor: skills/active/에 우리 방식으로 이식 후 등록
- reject: references.yaml에 "considered_and_rejected"로 기록 (재검토 방지)

## 절대 하지 말 것
- 사용자 컨펌 없이 dependency 추가
- last_commit_sha 환각 (실제 검증 불가능한 SHA 적기)
- 10개 모두 정밀 검토 (토큰 폭발)
