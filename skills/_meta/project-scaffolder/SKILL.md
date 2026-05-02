---
name: project-scaffolder
description: 새 프로젝트 부트스트랩 시 사용자와 대화하며 골격을 프로젝트에 맞게 채우는 메타 스킬. 처음 시작할 때 가장 먼저 트리거.
trigger:
  - "새 프로젝트 시작"
  - "프로젝트 부트스트랩"
  - "이 프로젝트를 시작해줘"
---

# Project Scaffolder

## 목적
빈 골격을 사용자의 프로젝트 목적에 맞게 채운다.

## 절차

### Step 1: 프로젝트 메타데이터 수집
사용자에게 다음을 묻고 AGENTS.md의 {{변수}}를 채운다:
- 프로젝트 이름
- 한 줄 목적
- 프로젝트 타입 (webapp / cli / lib / data-pipeline / api)
- 기술 스택 (빈 답 허용 — 나중에 결정 가능)

### Step 2: roles.yaml 모델 설정
사용자에게 사용할 Codex 모델을 묻고 config/roles.yaml의 {{사용자_설정_필요}}를 채운다.
- planner/implementer/researcher: 강한 모델 (예: gpt-5-codex)
- verifier/evaluator: 가벼운 모델 (예: gpt-5-mini)

### Step 3: 이전 프로젝트 import 게이트 (선택)
"이전에 만든 프로젝트가 있으면 거기서 가져올 자산이 있나요?" 묻기.
가져올 후보:
- active skill (다시 0회/0%부터 카운트 시작)
- references.yaml 항목
- decisions.md의 도메인 지식
- 일반화 가능한 골든 케이스

가져온 항목은 모두 candidate 상태로 시작 (active 즉시 진입 X).

### Step 4: 프로젝트 타입별 권장 설정
- webapp: rules/language/에 frontend, backend 규칙 자리 마련
- cli: rules/language/에 packaging, distribution 자리 마련
- lib: rules/language/에 api-design, semver 자리 마련
- data-pipeline: rules/common/에 idempotency 추가
- api: rules/common/에 versioning, rate-limit 추가

### Step 5: 외부 도입 후보 수집 (Researcher 트리거)
사용자에게 "이 프로젝트와 비슷한 기존 오픈소스 검색을 시작할까요?" 묻기.
승인하면 skills/_meta/research-evaluator를 호출.

### Step 6: 첫 plan 생성
plans/active/0001-bootstrap.md를 생성하고 사용자에게 "어디부터 시작할까요?" 묻기.

### Step 7: verify 게이트 첫 실행
./scripts/verify.sh 실행하여 빈 골격이 깨지지 않았는지 확인.

## 종료 조건
- AGENTS.md의 {{변수}}가 모두 채워짐
- config/roles.yaml의 모델이 채워짐
- plans/INDEX.md에 첫 plan 등록됨
- verify.sh 통과
