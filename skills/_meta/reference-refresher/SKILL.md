---
name: reference-refresher
description: references.yaml의 추적 repo를 갱신하고 변경사항을 우리 패턴에 반영할지 검토.
trigger:
  - "/refresh-references"
  - "레퍼런스 갱신"
---

# Reference Refresher

## 절차

### Step 1: 마지막 갱신 시점 확인
references.yaml의 last_refreshed 읽기. 30일 이상이면 사용자에게 알림.

### Step 2: 각 repo의 최신 commit 확인
GitHub API 또는 git ls-remote로 최신 commit SHA 가져오기.

### Step 3: 변경사항 요약
last_known_commit과 다르면:
- diff 통계 (커밋 수, 변경 파일)
- 주요 변경사항 (커밋 메시지 요약)

### Step 4: 우리 패턴 반영 후보 생성
변경사항 중 우리 import_targets에 영향 있는 것만 후보화.

### Step 5: 사용자 컨펌
"이 변경을 우리 골격에 반영할까요?" 표 형식으로 제시.

### Step 6: 반영 + last_known_commit 갱신
사용자 OK 시 변경 반영, references.yaml 갱신, last_refreshed 갱신.

## 절대 하지 말 것
- 사용자 컨펌 없이 자동 반영
- last_known_commit 검증 없이 갱신
