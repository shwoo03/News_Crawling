# 권고 디렉터리 레이아웃

## 한 문장 정의

이 문서는 이 뼈대에서 출발한 프로젝트가 소스·테스트·문서를 어디에 둘지 정하는 **권고** 레이아웃입니다.

## 무엇을 하는가

뼈대가 복사한 디렉터리(`docs/`, `scripts/`, `rules/`, `runtime/`, `knowledge/`, `codex/`, `.claude/`, `tests/`, `examples/`)는 고정입니다. 프로젝트가 **새로 만드는 코드**가 어디에 들어가야 하는지를 권고합니다. verify-skeleton은 이 레이아웃을 강제하지 않습니다(누락은 경고 아님). 그러나 새 프로젝트가 이유 없이 벗어나면 인수인계와 검색이 어려워집니다.

## 왜 필요한가

새 프로젝트마다 "소스는 `src/`인가 `lib/`인가", "통합 테스트는 `tests/integration/`인가 `e2e/`인가"를 다시 결정하면 에이전트가 매번 다른 가정을 합니다. 초기에 합의해두면 다음 세션과 다른 에이전트가 같은 곳을 찾습니다.

## 권고 레이아웃

```
<project-root>/
├── AGENTS.md                # 뼈대 고정
├── CLAUDE.md                # 뼈대 고정
├── README.md                # 프로젝트 진입점 (자유롭게 수정)
├── docs/                    # 뼈대 고정 + 프로젝트별 문서 추가
│   ├── PROJECT_PROFILE.md   # 필수, 사용자 답변으로 채움
│   ├── PROJECT_SPEC.md      # 선택, 수용 테스트 필요할 때만
│   └── PROJECT_OPERATING_PLAN.md  # 선택
├── rules/                   # 뼈대 고정
├── codex/                   # 뼈대 고정
├── .claude/                 # 뼈대 고정 (skills, settings.local.json)
├── knowledge/               # 뼈대 고정 (index.md + log.md + 등)
├── runtime/                 # 뼈대 고정 (logs, state, archive, external clones)
├── scripts/                 # 뼈대 고정 + 프로젝트별 자동화 추가
├── tests/                   # 뼈대 고정 (smoke) + 프로젝트 테스트 추가
├── examples/                # 뼈대 고정 (참조 전용)
├── research/                # ★ 외부 후보, 조사 결과, 적용 전 근거
│
├── src/                     # ★ 프로젝트 소스 코드의 기본 위치
│   └── <package>/...        # 단일 언어면 src/ 아래, 멀티면 src/<lang>/
├── tests/unit/              # ★ 단위 테스트
├── tests/integration/       # ★ 통합 테스트
└── data/                    # ★ 재현 가능한 샘플 데이터 (git 관리)
```

★ 표시는 프로젝트가 **새로 추가**하는 영역입니다.

## 세부 규칙

### 소스 위치

- **단일 언어**: 소스는 `src/` 또는 `src/<package>/`에 둡니다. 루트에 소스 파일을 흩어놓지 않습니다.
- **멀티 언어**: `src/python/`, `src/ts/`처럼 언어별 디렉터리로 나눕니다. 또는 각 언어의 관용 위치(`src/`, `web/`)를 프로젝트 프로필에 기록합니다.
- **프레임워크 관용 구조**가 있으면(예: Next.js `app/`, Rails `app/`) 관용을 따르고 PROJECT_PROFILE에 기록합니다. 관용과 충돌시 관용이 우선합니다.

### 테스트 위치

- 단위 테스트: `tests/unit/` 또는 소스 옆(`src/foo/foo_test.py`). 언어 관용을 따릅니다.
- 통합·E2E 테스트: `tests/integration/` 또는 `tests/e2e/`.
- 뼈대의 `tests/test_smoke.py`는 뼈대 자체의 스모크입니다. 프로젝트 로직 테스트와 섞지 않습니다.
- 테스트 픽스처: `tests/fixtures/` 또는 `tests/data/`. 프로덕션 `data/`와 구분.

### 산출물·캐시·임시

- 빌드 산출물(`dist/`, `build/`, `target/`), 의존성 디렉터리(`node_modules/`, `.venv/`), 캐시(`.pytest_cache/`, `__pycache__/`)는 **프로젝트 관리 외부**입니다. 커밋하지 않습니다.
- 런타임 상태는 `runtime/`(뼈대 고정)만 씁니다. 소스와 섞지 않습니다.
- 외부 오픈소스 저장소를 clone해 분석할 때는 `runtime/external-repos/<host>/<owner>__<repo>/`를 사용합니다. clone 원본은 런타임 분석 대상이며 프로젝트 소스, 문서, 연구 카드가 아닙니다.
- 일회성 실험·디버그 파일은 `rules/common/ephemeral-files.md`를 따릅니다.

### 문서 위치

- 운영 문서(프로필/스펙/계획)는 `docs/` 직속.
- 설계·아키텍처 노트는 `docs/architecture/` 또는 `docs/_meta/`.
- 외부 레퍼런스 중 아직 채택되지 않은 후보와 검색 근거는 `research/reference-candidates/`.
- 외부 repo clone 원본은 `research/`가 아니라 `runtime/external-repos/`.
- 채택되어 장기 설명으로 승격된 외부 레퍼런스 메모는 `docs/_meta/`.
- 프로젝트별 런북·플레이북은 `docs/runbooks/`.
- `knowledge/`는 **장기 지식**용이며 사람이 수동으로만 편집합니다.

### 설정 파일

- 루트에 두는 파일: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile`, `Dockerfile` 등 툴 관용.
- 빌드 시스템 파일은 루트에만 두고, 서브디렉터리에 중복 생성하지 않습니다.

## 예외와 조정

- 언어·프레임워크 관용과 충돌하면 **관용이 우선**입니다. 예외는 `docs/PROJECT_PROFILE.md`의 `project_specific_notes`에 이유와 함께 기록합니다.
- 기존 프로젝트에 뼈대를 **얹을 때**는 기존 구조를 해치지 않습니다. 뼈대 고정 디렉터리는 그대로 추가하고, 소스는 이미 있는 곳을 유지합니다.

## 결과는 무엇인가

이 레이아웃을 지키면 다음이 확보됩니다.

- 다음 에이전트·사람이 "소스가 어디"를 추측하지 않습니다.
- `scripts/verify-skeleton.py`는 뼈대 고정 경계만 검사하고, 프로젝트 소스는 자유롭게 진화합니다.
- 산출물·캐시·임시 파일이 소스와 섞이지 않아 검색·grep이 빨라집니다.

## 기능 추가/수정 판단 기준

새 디렉터리를 권고에 추가할 때는 **여러 도메인 프로젝트에서 반복적으로 필요해진 후**에 추가합니다. 한 프로젝트에만 필요하면 그 프로젝트의 `PROJECT_PROFILE.md`에 기록합니다. 뼈대 고정 영역을 건드리는 변경은 `docs/SKELETON_UPGRADE.md`를 먼저 참고합니다.

## 구현 연결 정보

- 상위 규칙 인덱스: `rules/common/README.md`
- 임시 파일 수명 규칙: `rules/common/ephemeral-files.md`
- 뼈대 업그레이드 가이드: `docs/SKELETON_UPGRADE.md`
- 외부 사례 탐색 워크플로: `docs/REFERENCE_DISCOVERY_WORKFLOW.md`
- 외부 저장소 clone 작업 공간: `runtime/external-repos/README.md`
- 프로젝트 프로필: `docs/PROJECT_PROFILE.template.md`
