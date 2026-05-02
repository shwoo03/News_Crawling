# 프로젝트 프로필 예시: CTF Solver

## 한 문장 정의

CTF 문제 풀이와 익스플로잇 작성 흐름을 재현 가능한 스크립트와 실행 기록으로 관리하는 프로젝트 예시입니다.

## 기본 정보

- `project_name`: ctf-solver-example
- `domain`: 보안 연구와 CTF 익스플로잇 개발
- `owner`: ctf-team
- `status`: planning
- `created_at`: 2026-04-23

## 목표

- `primary_goal`: 선택한 CTF 문제의 플래그 획득 과정을 로컬에서 재현 가능한 solver와 exploit runbook으로 만든다.
- `target_users`: CTF 참가자와 팀 리뷰어.
- `success_criteria`: solver가 로컬에서 플래그 획득을 재현하고, exploit 단계가 스크립트화되어 있으며, 가정과 환경이 팀원이 다시 실행할 수 있게 기록되어 있다.
- `failure_definition`: solver가 한 번만 동작하거나, 숨은 머신 상태에 의존하거나, 다른 팀원이 재실행할 수 없다.
- `non_goals`: 실전 공격용 production-grade 도구 제작.

## 프로젝트별 맥락

- `stack`: Python, pwntools, GDB, Docker
- `runtime_environment`: challenge binary를 포함한 로컬 Linux 컨테이너
- `data_sources`: challenge binary, pcap, 문제 설명
- `external_dependencies`: libc database, disassembler tools
- `security_or_privacy_constraints`: payload는 제공된 challenge target에만 제한하며, 제공 범위를 넘는 scanning은 하지 않는다.
- `compatibility_constraints`: local 실행과 remote host/port endpoint를 모두 지원한다.
- `project_specific_notes`: libc와 입력 seed를 고정해 exploit 재현성을 유지한다.

## 활성 운영 선택

- `active_workflows`: exploit-hypothesis-loop, plan-execute-validate-record
- `active_skills`: search-first, tdd-workflow, verification-loop, security-review
- `active_rules`: validate-each-step, preserve-artifacts, append-only-logs
- `validation_summary`: exploit을 여러 번 실행해 flag 획득과 control proof를 확인한다.
- `pivot_summary`: 두 개의 exploit path가 막히면 다른 primitive로 전환한다.

## 기능 추가/수정 판단 기준

새 자동화는 반복되는 풀이 단계가 있고 재현성 검증이 가능할 때만 추가합니다. 단발성 문제 풀이 메모는 스킬이나 워크플로가 아니라 runtime evidence 또는 문제별 runbook으로 둡니다.
