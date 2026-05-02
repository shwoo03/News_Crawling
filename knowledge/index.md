# 지식 인덱스

프로젝트의 장기 지식을 한 줄씩 정리하는 범위 제한 인덱스입니다. 상세 내용은
`knowledge/log.md`, `knowledge/project-registry.md`, 또는 프로젝트별 파일에 둡니다.

| ID | 주제 | 상태 | 출처 | Superseded By | Superseded At |
| --- | --- | --- | --- | --- | --- |
| K000 | 프로젝트 News_Crawling 를 skeleton에서 초기화했습니다. | active | `runtime/activity-log.jsonl:1` | - | - |
| K001 | 프로젝트 레지스트리에 재사용 가능한 결과와 회수 기록을 보존합니다. | active | `knowledge/project-registry.md:1` | - | - |

## 인덱스 규칙

- 지식 항목마다 한 줄씩만 씁니다.
- 요약은 짧게 유지합니다.
- 안정된 ID를 유지합니다.
- 모든 항목은 출처(activity-log ts, file:line, URL 중 하나)를 포함해야 합니다.
- 항목이 교체(superseded)되면 원래 행을 남기고 `superseded_by`와 `superseded_at`(`YYYY-MM-DD`)만 채웁니다.
- 본문에 긴 참고자료를 붙여넣지 않습니다.
- 상세 출처는 링크로만 연결합니다.
