#!/usr/bin/env python3
"""Check tracked external repositories for new commits.

The script is intentionally review-first: it reports differences and, in
`--write-proposals` mode, creates review proposal stubs. It never updates
`references.yaml` by itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import convert as convert_lib


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


@dataclass
class ReferenceStatus:
    name: str
    url: str
    last_known_commit: str | None
    latest_commit: str | None
    status: str
    detail: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_references(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    repos: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_repos = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = convert_lib._strip_comment(raw)
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped == "repos:":
            in_repos = True
            continue
        if not in_repos:
            continue
        if stripped.startswith("- "):
            if current:
                repos.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        current[key.strip()] = convert_lib._parse_scalar(value)
    if current:
        repos.append(current)
    return repos


def latest_commit(url: str, timeout: int) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.SubprocessError as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()
    first = result.stdout.strip().split()
    if not first:
        return None, "empty git ls-remote output"
    return first[0], None


def check_references(root: Path, *, no_network: bool, timeout: int) -> list[ReferenceStatus]:
    statuses: list[ReferenceStatus] = []
    for repo in parse_references(root / "references.yaml"):
        name = str(repo.get("name") or repo.get("url") or "unnamed")
        url = str(repo.get("url") or "")
        last_known = repo.get("last_known_commit")
        if not url:
            statuses.append(ReferenceStatus(name, "", None, None, "ERROR", "missing url"))
            continue
        if no_network:
            statuses.append(ReferenceStatus(name, url, last_known, None, "SKIP", "network disabled"))
            continue
        latest, error = latest_commit(url, timeout)
        if error:
            statuses.append(ReferenceStatus(name, url, last_known, latest, "ERROR", error))
        elif latest != last_known:
            statuses.append(ReferenceStatus(name, url, last_known, latest, "CHANGED", "user review required before updating references.yaml"))
        else:
            statuses.append(ReferenceStatus(name, url, last_known, latest, "OK", "unchanged"))
    return statuses


def write_proposals(root: Path, statuses: list[ReferenceStatus]) -> list[str]:
    written: list[str] = []
    proposal_dir = root / "runtime" / "proposals" / "reference-adoption"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    for status in statuses:
        if status.status != "CHANGED":
            continue
        slug = "".join(ch if ch.isalnum() else "-" for ch in status.name.lower()).strip("-") or "repo"
        path = proposal_dir / f"{today}-{slug}-refresh.md"
        if path.exists():
            continue
        body = f"""# Reference Refresh: {status.name}

## 상태

- `status`: proposed
- `created_at`: {today}
- `candidate_card`: `references.yaml`
- `proposal_type`: reference_refresh
- `approval_required`: yes
- `decision_source`:

## 한 문장 정의

`{status.name}`의 최신 commit을 확인했고, 기존 기록과 달라 사용자 검토가 필요합니다.

## 근거

- repo: {status.url}
- last_known_commit: {status.last_known_commit}
- latest_commit: {status.latest_commit}

## 제안 변경

- 승인되면 `references.yaml`의 `last_known_commit`과 `last_checked`를 갱신합니다.
- import_targets에 영향 있는 변경만 별도 후보 카드로 승격합니다.

## 검증 계획

```powershell
python scripts/verify-skeleton.py
python scripts/validate-reference-proposals.py
```

## 최종 결정 기록

- `decision`: pending
- `decided_at`:
- `decided_by`:
- `decision_source`:
- `applied_in`:
- `validation_result`:
"""
        path.write_text(body, encoding="utf-8")
        written.append(path.relative_to(root).as_posix())
    return written


def render_text(statuses: list[ReferenceStatus], written: list[str]) -> str:
    if not statuses:
        return "no repositories configured in references.yaml"
    lines = ["Reference Refresh"]
    for status in statuses:
        lines.append(f"  {status.status:<7} {status.name}: {status.detail}")
        if status.latest_commit:
            lines.append(f"          {status.last_known_commit} -> {status.latest_commit}")
    for path in written:
        lines.append(f"  proposal: {path}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--no-network", action="store_true", help="Do not call git ls-remote; report configured repos only.")
    parser.add_argument("--timeout", type=int, default=20, help="Per-repo git timeout in seconds.")
    parser.add_argument("--write-proposals", action="store_true", help="Write review proposal stubs for changed repos.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    statuses = check_references(root, no_network=args.no_network, timeout=args.timeout)
    written = write_proposals(root, statuses) if args.write_proposals else []
    if args.format == "json":
        print(json.dumps({"root": str(root), "statuses": [asdict(s) for s in statuses], "written": written}, ensure_ascii=False, indent=2))
    else:
        print(render_text(statuses, written))
    return 1 if any(status.status == "ERROR" for status in statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
