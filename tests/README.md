# Skeleton smoke tests

## 한 문장 정의

스켈레톤 유지보수 PR이 `scripts/*` 또는 `docs/*`를 바꿨을 때 빠르게 회귀를 잡기 위한 최소 스모크 테스트 묶음입니다.

## 무엇을 하는가

`python -m unittest discover tests` 한 줄로 다음을 확인합니다.

1. 모든 `scripts/**/*.py`가 `py_compile`로 바이트컴파일된다 — 문법 오류 즉시 검출.
2. 주요 스크립트 4종(`verify-skeleton`, `rotate-activity-log`, `wiki-lint`, `bootstrap/new-project`)이 `--help`를 exit 0으로 출력한다 — argparse 사용성 보장.
3. `scripts/verify-skeleton.py --skip-wiki-lint`가 스켈레톤 자신에 대해 exit 0을 낸다 — 구조 건강성.
4. `scripts/bootstrap/new-project.py`가 임시 디렉터리에 프로젝트를 만들고, 그 결과물에 대해 `verify-skeleton.py`를 돌려도 exit 0이다 — 부트스트랩이 출력하는 프로젝트가 자체적으로 건강함.
5. `scripts/rotate-activity-log.py`의 dry-run이 exit 0이다 — 로테이션 플래너가 크래시하지 않음.

## 왜 필요한가

CI 파일(`.github/workflows/*`)은 이 스켈레톤에 의도적으로 없습니다(복사해서 쓰는 템플릿이라 CI는 프로젝트별). 대신 `python -m unittest discover tests`가 "PR 전에 돌려봐야 할 한 줄"입니다. 빠르고(보통 5초 이내), 외부 의존성이 없습니다(표준 라이브러리만).

## 어떻게 실행하는가

```
python -m unittest discover -s tests -v
```

## 설계 메모

- `pytest`가 아닌 `unittest`를 쓰는 이유: 스켈레톤에 외부 의존성을 도입하지 않기 위함.
- `post-tool-use-log.py`는 파일명에 하이픈이 있어 import 불가이며, stdin/argv 기반 서브프로세스로만 호출되는 게 의도된 계약입니다. 본 테스트는 subprocess로만 다룹니다.
- 테스트는 모두 임시 디렉터리에서 동작하고 스켈레톤 자체 파일(runtime/activity-log.jsonl 등)은 건드리지 않습니다.
