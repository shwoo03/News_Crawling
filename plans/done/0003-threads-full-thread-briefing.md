# Plan 0003: Threads Full Thread Briefing

## Status

done

## Goal

Threads 수집기가 첫 포스트만 요약하지 않고 같은 작성자의 연속 스레드 전체를 본문으로 조립한 뒤, 더 자세한 3/5/3 브리핑 형식으로 Discord 웹훅에 전송하게 만든다.

## Scope

- Threads 상세 페이지의 렌더링 텍스트에서 작성자 본문과 번호 매겨진 후속 포스트를 추출한다.
- 요약 구조를 `lead + summary 3개 + highlights 5개 + importance 3개`로 조정한다.
- Discord embed 설명과 필드 길이를 안전하게 제한한다.
- Docker 컨테이너에서 테스트와 실제 웹훅 전송을 검증한다.

## Acceptance

- Docker 테스트에서 Threads 전체 스레드 추출 케이스가 통과한다.
- 실제 Threads 최신 글 추출 결과에 `1/`, `2/`, `7/` 같은 후속 포스트가 포함된다.
- Discord 웹훅 테스트 전송이 성공한다.

## Result

- Threads 상세 페이지에서 렌더링된 `body.innerText`를 읽어 작성자 본문 블록을 우선 추출한다.
- 번호가 있는 스레드는 도입 포스트와 `1/`, `2/`, `3/` 순번 블록을 이어 붙인다.
- 번호가 없는 스레드는 첫 작성자 본문부터 댓글/다른 텍스트로 끊기기 전까지의 작성자 연속 구간만 보수적으로 이어 붙인다.
- 전체 스레드 추출 결과가 비어 있으면 기존 HTML 단일 본문 추출로 fallback한다.
- Docker 테스트 17개 통과, 실제 Threads 최신 글 추출에서 `1/`, `2/`, `7/` 포함 확인, Discord 웹훅 전송 확인 완료.
