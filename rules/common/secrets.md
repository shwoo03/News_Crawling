# Secrets

- 절대 코드·로그·plan에 평문 시크릿 쓰지 말 것
- .env.template만 골격에 포함, .env는 .gitignore
- API 키는 환경변수 또는 시크릿 매니저 참조
- 시크릿 노출 시 즉시 회전 + state/decisions.md에 기록
