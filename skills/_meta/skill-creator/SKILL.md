---
name: skill-creator
description: 새 skill을 표준 형식으로 생성하는 절차. 골든 케이스 동시 작성 권장.
trigger:
  - "새 skill 만들기"
  - "패턴을 skill로"
---

# Skill Creator

## 절차

### Step 1: 위치 결정
- 사용자 직접 추가: skills/active/<name>/
- AI가 패턴 발견: skills/_candidates/<name>/

### Step 2: 템플릿 복제
skills/_templates/SKILL.template.md를 복제.

### Step 3: frontmatter 채우기
필수 필드:
- name
- description (다른 skill과 의미 충돌 없는지 확인)
- trigger (어떤 입력에 발동)
- created_at
- success_rate: null (아직 측정 전)
- use_count: 0

### Step 4: 충돌 검사
기존 skill의 description·trigger와 의미 겹치는지 확인.
겹치면 사용자에게 보고하고 합치기 / 따로 두기 결정.

### Step 5: 골든 케이스 동시 작성 (권장)
skills/<name>/goldens/case-001.yaml 생성.
1~3개 권장, 0개도 허용 (단 회귀 검증 못 함).

### Step 6: manifest 갱신
manifest.yaml에 skill 등록 (수동 변환 시).

### Step 7: verify
scripts/verify.sh 실행. 통과해야 commit 가능.

## Progressive Disclosure 가이드
자세한 skill bundle 작성 규칙은 references/progressive-disclosure.md를 따른다.

## frontmatter 표준
```yaml
---
name: <kebab-case>
description: <한 문장, 다른 skill과 충돌하지 않는 고유 트리거 설명>
trigger:
  - <키워드 또는 의도>
created_at: <ISO date>
status: candidate | active | deprecated
use_count: 0
success_count: 0
last_used_at: null
goldens_count: 0
---
```
