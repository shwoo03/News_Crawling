# <후보 이름>

## 기본 정보

- `name`:
- `url`:
- `source_type`: repository | official_docs | article | paper | existing_reference
- `status`: new | reviewing | proposed | adopted | deferred | rejected
- `searched_for`:
- `created_at`:
- `reviewed_at`:
- `reviewer`:
- `query_provenance`:
- `candidate_rank`:
- `candidate_count`:

## 왜 보는가

- `problem_statement`:
- `why_it_matters`:
- `expected_value`:

## 유용한 패턴

- `useful_patterns`:
  - 
- `what_to_copy_conceptually`:
  - 
- `what_to_copy_directly`:
  - 
- `what_not_to_copy`:
  - 

## 구조 분석

- `module_inventory`:
  - 
- `reusable_units`:
  - 

## 증거

- `evidence_summary`:
- `local_clone_path`: not cloned | runtime/external-repos/<host>/<owner>__<repo>
- `checked_revision`: not checked | <commit/tag/branch>
- `freshness_signal`:
- `maintenance_signal`:
- `documentation_signal`:
- `validation_signal`:
- `sources`:
  - {"path":"<source path or URL>","kind":"readme|source_file|docs|test|manifest","evidence":"<what this source proves>","hash_or_line_ref":"<hash or line reference>"}

## 리스크

- `license`:
- `security_or_privacy_risk`:
- `maintenance_risk`:
- `complexity_risk`:
- `dependency_risk`:
- `fit_risk`:

## 적용 후보

- `applies_to`: docs | rules | skills | scripts | tests | runtime | notion | other
- `target_files_or_areas`:
  - 
- `adoption_decision`: adopt | adapt | copy | direct_implementation | defer | reject
- `absorption_mode`: dependency | wrapper | partial_copy | concept_only | direct_implementation | mixed
- `direct_implementation_reason`: not applicable | <왜 dependency/wrapper/partial_copy/concept_only가 부적합한지>
- `decision_reason`:
- `next_action`:

## 점수

| 기준 | 배점 | 점수 | 근거 |
| --- | ---: | ---: | --- |
| 문제 적합성 | 20 |  |  |
| 구조 명확성 | 15 |  |  |
| 검증 가능성 | 15 |  |  |
| 유지보수 신호 | 15 |  |  |
| 흡수 비용 | 15 |  |  |
| 보안/라이선스 리스크 | 10 |  |  |
| 설명 가치 | 10 |  |  |
| 합계 | 100 |  |  |

## Dry-Run 제안

- `proposal_needed`: yes | no
- `files_to_change`:
  - 
- `behavior_change`:
- `validation_plan`:
- `rollback_or_stop_condition`:
- `approval_required`: yes
- `copy_boundary`: not applicable | private local only; record source, license, revision, copied files/functions, and review again before redistribution

## 최종 기록

- `final_status`:
- `implemented_in`:
  - 
- `validation_result`:
- `activity_log_entry`:
- `notes`:
