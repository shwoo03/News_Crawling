---
name: replan-on-blocker
description: 구현 중 막혔을 때 재계획하는 표준 절차. 같은 task에서 3회 초과 시 자동 정지.
trigger:
  - "막힘"
  - "재계획 필요"
  - "blocker"
---

# Replan on Blocker

## 절차

### Step 1: 현재 plan의 replan_count 확인
plans/active/<현재>.md의 frontmatter에서 replan_count 읽기.

### Step 2: 3회 초과 검사
replan_count >= 3 이면:
- state/blockers.md에 기록
- plan을 plans/failed/로 이동
- 사용자에게 보고하고 정지
- 절대 4번째 재계획 시도하지 말 것

### Step 3: 막힌 이유 누적 (덮어쓰기 X)
plan 파일 끝에 다음 섹션 append:

```
## Replan #{{n}} — {{timestamp}}
### 이전 시도 요약
- 무엇을 시도했나
- 왜 실패했나
- 무엇을 배웠나

### 새 접근
- 시도할 것
- 회피할 것 (이전 시도와 다른 점)
```

### Step 4: replan_count++ 후 재시도
plan frontmatter의 replan_count 증가, 새 접근으로 진행.

## 절대 하지 말 것
- replan_count 리셋
- 이전 시도 섹션 덮어쓰기
- 같은 접근으로 재시도
