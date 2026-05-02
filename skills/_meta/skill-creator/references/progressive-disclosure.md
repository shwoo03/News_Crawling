# Progressive Disclosure

## 목적
skill은 필요한 정보만 먼저 읽고, 자세한 정보는 필요할 때 참조하도록 구성한다.

## 기본 구조
- SKILL.md: 트리거, 핵심 절차, 직접 참조 링크
- references/: SKILL.md에서 직접 링크하는 참조 자료
- scripts/: 한 번의 작업을 수행하는 작은 도구
- assets/: 엄격한 출력 형식과 템플릿
- goldens/: 회귀 평가 케이스

## 추가 베스트 프랙티스

### 참조 파일 깊이 제한
모든 reference 파일은 SKILL.md에서 직접 링크해야 한다. 두 번째 수준의 하위 디렉터리를 만들지 않는다.

### 긴 reference 파일의 목차
100줄을 초과하는 reference 파일에는 맨 위에 "Contents" 섹션을 포함해 주요 목차를 나열한다. 부분 읽기를 할 때 전체 구조를 파악할 수 있도록 돕는다.

### 워크플로와 피드백 루프 작성
복잡한 작업은 체크리스트와 검증 루프를 포함하여 단계별로 작성한다.

Copy this checklist:
- Step 1: 입력과 제약을 확인한다.
- Step 2: 필요한 참조 파일만 읽는다.
- Step 3: 작업을 수행한다.
- Step 4: validator를 실행한다.
- Step 5: 오류를 수정하고 통과할 때까지 반복한다.

Feedback loop:
- Run validator
- Fix errors
- Repeat until validation passes

### 시간에 민감한 내용 처리
기술의 변화나 API 버전 같은 시한부 정보는 "Old patterns"라는 접을 수 있는 details 블록에 넣어 현재와 분리한다.

### 용어와 명칭 일관성
스킬 전반에 걸쳐 동일한 용어를 사용한다. 예: "사용자 ID"를 "유저 아이디"로 표현하지 않는다.

### 템플릿 사용
정해진 형식의 출력이 필요한 경우 assets/에 템플릿을 저장하고 이를 참조한다.

### 3인칭 명령형과 번호 사용
본문에서 지시할 때는 "추출한다", "검증한다"와 같이 3인칭 명령형을 사용하고 단계 번호를 명시한다.

### 경로와 파일 규칙
경로는 항상 슬래시(/)를 사용한다. README.md, CHANGELOG.md와 같은 사람용 문서를 references/에 넣지 않는다. 장기 유지가 필요한 코드는 scripts/가 아닌 리포지터리의 일반 디렉터리에 보관한다.
