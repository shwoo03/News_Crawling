# 프로젝트 프로필 템플릿

이 파일을 각 프로젝트의 `docs/PROJECT_PROFILE.md`로 복사해 사용합니다. 사용자가 새 프로젝트를 시작할 때 직접 채워야 하는 최소 문서입니다.

## 한 문장 정의

프로젝트 프로필은 현재 프로젝트의 목표, 사용자, 성공 기준, 실패 기준, 제약 조건을 담는 얇은 운영 계약입니다.

## 무엇을 하는가

프로젝트별 사실만 담습니다. 공통 방법론, 긴 프롬프트, 일반 규칙, 반복 절차는 넣지 않습니다. 프로필이 만들어진 뒤 에이전트는 부족한 정보를 질문하고, 실제 필요가 생길 때만 명세, 운영 계획, 워크플로, 스킬을 추가합니다.

## 왜 필요한가

프로젝트 프로필이 얇고 명확해야 에이전트가 “이 프로젝트가 무엇을 성공으로 보는지” 잃지 않습니다. 공통 방법론과 프로젝트 사실이 섞이면 새 프로젝트에 잘못 복사되고, 사용자가 무엇을 결정해야 하는지도 흐려집니다.

## 기본 정보

- `project_name`:
- `domain`:
- `owner`:
- `status`: planning
- `created_at`:

## 목표

- `primary_goal`:
- `target_users`:
- `success_criteria`:
- `failure_definition`:
- `non_goals`:

## 프로젝트별 맥락

- `stack`:
- `runtime_environment`:
- `data_sources`:
- `external_dependencies`:
- `security_or_privacy_constraints`:
- `compatibility_constraints`:
- `project_specific_notes`:

## 활성 운영 선택 (선택 — 에이전트가 나중에 채움)

이 섹션은 **사용자가 직접 채우지 않아도 됩니다.** 프로젝트가 진행되면서 반복되는 작업이 확인되면 에이전트가 제안해 채웁니다. 초기에는 전부 비어 있거나 `TBD`로 둡니다. 예시 파일(`examples/*/PROJECT_PROFILE.md`)에 채워진 값들은 이미 성숙한 프로젝트의 스냅샷이며, 신규 프로젝트가 처음부터 알 수 있는 값이 아닙니다.

- `active_workflows`:
- `active_skills`:
- `active_rules`:
- `validation_summary`:
- `pivot_summary`:

## 첫 반복 체크리스트

- [ ] 목표가 한 문장으로 쓰였습니다.
- [ ] 성공 기준과 실패 기준이 측정 가능합니다.
- [ ] 기술 스택과 제약 조건이 명확합니다.
- [ ] 모르는 항목은 `[NEEDS CLARIFICATION: <specific question>]` 또는 명시적 보류용 `TBD`로 표시했습니다.
- [ ] 이미 아는 경우에만 활성 스킬과 워크플로를 적었습니다.
- [ ] 이미 아는 경우에만 마이크로 검증을 요약했습니다.
- [ ] 알려진 오픈소스, 경쟁 제품, 공식 문서, 기존 레퍼런스는 후보 카드로 처리했거나 명시적으로 없음/TBD로 표시했습니다.
- [ ] 프로젝트별 예외가 있다면 문서화했습니다.

## 결과는 무엇인가

이 프로필이 채워지면 에이전트는 다음을 판단할 수 있습니다.

- 지금 만들려는 것이 무엇인지
- 누구를 위해 만드는지
- 성공과 실패를 어떻게 구분할지
- 어떤 제약을 넘으면 안 되는지
- 어떤 워크플로와 스킬을 쓸 수 있는지
- 다음에 질문해야 할 빈칸이 무엇인지

## 기능 추가/수정 판단 기준

프로필에는 현재 프로젝트의 사실만 추가합니다. 반복 절차는 스킬로, 모든 프로젝트에 적용되는 규칙은 공통 규칙으로, 구현 정답 조건은 프로젝트 명세로 보냅니다. 프로필이 길어지고 있다면 대부분 다른 문서로 옮겨야 한다는 신호입니다.

## Agent Fill-In Contract

에이전트가 이 프로필을 읽으면 다음을 수행합니다.

1. 다음 행동을 막는 누락 항목을 찾습니다.
2. 사용자에게 한 번에 한두 개의 구체적인 후속 질문만 합니다.
3. 사용자가 말하지 않은 사실은 만들지 않습니다.
4. 모르는 항목은 `[NEEDS CLARIFICATION: <specific question>]`로 표시합니다.
5. 사용자가 명확히 나중으로 미룬 항목은 `TBD`로 둘 수 있습니다.
6. 사용자가 확인한 항목만 프로필에 반영합니다.
7. 구현 정답 조건이 필요할 때만 프로젝트 명세를 만듭니다.
8. 맞춤 검증, 권한, 피벗 기준이 필요할 때만 프로젝트 운영 계획을 만듭니다.
9. 반복되는 프로젝트 워크플로가 확인될 때만 프로젝트별 스킬을 추가합니다.
10. 부트스트랩 행동은 활동 로그에 남깁니다.

### 대화 질문 순서 (cold start에서 사용)

사용자가 "시작하자" 같은 짧은 말만 하거나 목표를 미리 말하지 않은 경우, 아래 순서로 질문합니다. 한 번에 한두 개만 묻고, 답을 받으면 프로필에 반영한 뒤 다음으로 갑니다. 기본 정보(`project_name`, `domain`, `stack`)는 부트스트랩 때 이미 채워져 있으므로 다시 묻지 않습니다.

| 순서 | 필드 | 한국어 질문 예시 |
| --- | --- | --- |
| 1 | `primary_goal` | "이 프로젝트가 끝났을 때 최종 사용자가 무엇을 할 수 있게 돼야 하나요? 한 문장으로 말씀해 주세요." |
| 2 | `target_users` | "이걸 누가 쓰게 되나요? (사람 역할 기준, 시스템 말고)" |
| 3 | `success_criteria` | "성공을 어떻게 확인할 수 있나요? 가능하면 숫자나 테스트 기준으로요." |
| 4 | `failure_definition` | "어떤 결과가 나오면 실패로 봐야 하나요?" |
| 5 | `non_goals` | "이 프로젝트가 **하지 않을** 일이 있나요? (범위 밖으로 미리 제외할 것)" |
| 6 | `security_or_privacy_constraints` | "데이터에 개인정보가 있거나, 보안/컴플라이언스 제약이 있나요?" |
| 7 | `compatibility_constraints` | "기존 시스템이나 API와의 호환 조건이 있나요?" |
| 8 | `data_sources`, `external_dependencies` | "어떤 데이터를 읽고, 외부 서비스(API, DB 등)에 의존하나요? 참고해야 할 오픈소스, 경쟁 제품, 공식 문서, 기존 레퍼런스가 있나요?" |
| 9 | `runtime_environment` | "로컬 노트북, Docker, 클라우드 중 어디서 돌아가나요?" |
| 10 | `project_specific_notes` | "이 프로젝트만의 특이 사항이 있나요? (재현성, 버전 핀 등)" |

"## 활성 운영 선택" 섹션(`active_workflows`, `active_skills`, `active_rules`, `validation_summary`, `pivot_summary`)은 cold start에서 묻지 않습니다. 프로젝트 진행 중 반복 패턴이 보이면 에이전트가 제안해 채웁니다.

1~5까지 채워지면 PROFILE v1이 완성된 것으로 보고 사용자에게 "여기까지 확인하시겠어요?"로 첫 체크포인트를 만듭니다. 나머지는 실제 필요가 생길 때 추가합니다.

레퍼런스가 언급되면 에이전트는 구현을 시작하기 전에 `docs/REFERENCE_DISCOVERY_WORKFLOW.md`를 따라 후보 카드로 정리합니다. 저장소 구조 분석이 필요하면 원본은 `runtime/external-repos/` 아래에 clone하고, 장기 규칙이나 코드 구조 반영은 dry-run 제안과 사용자 승인 뒤에만 진행합니다.

### 명확화 표시 예시

```text
- `primary_goal`: [NEEDS CLARIFICATION: 최종 사용자가 완료해야 하는 행동은 무엇인가?]
- `stack`: [NEEDS CLARIFICATION: Python만 확정인가, TypeScript도 범위에 포함되는가?]
- `success_criteria`: [NEEDS CLARIFICATION: 정확도, 지연 시간, 완료율 중 어떤 숫자 기준이 필요한가?]
```

미해결 질문 검색 예시 (플랫폼에 맞게 택1):

```text
rg "NEEDS CLARIFICATION" docs                                       # ripgrep (cross-platform)
grep -rn "NEEDS CLARIFICATION" docs                                 # POSIX (macOS/Linux)
Select-String -Path docs\*.md -Pattern "NEEDS CLARIFICATION" -Recurse  # Windows PowerShell
```
