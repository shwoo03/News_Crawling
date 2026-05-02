# Go Rules Pack

- Prefer small packages with explicit interfaces only at package boundaries.
- Use `go test ./...` as the default unit/smoke check when Go files exist.
- Keep generated files and vendored dependencies out of harness canonical rules unless the project explicitly opts in.
