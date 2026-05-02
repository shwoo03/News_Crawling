# 언어별 규칙

## 한 문장 정의

이 디렉터리는 특정 기술 스택을 사용할 때만 적용되는 안정적이고 재사용 가능한 규칙을 담습니다.

현재 시드 모듈:

- `python/README.md`
- `typescript/README.md`
- `go/README.md`
- `rust/README.md`
- `web/README.md`

프로젝트가 실제로 해당 스택을 사용할 때만 언어별 규칙을 활성 운영에 반영합니다. 각 디렉터리는 `rules/common/`을 확장하는 opt-in 가이드입니다.

프로젝트별 스택 메모는 `docs/PROJECT_PROFILE.md`에 두고, 재사용 가능한 언어 규칙은 이 디렉터리에 둡니다.
