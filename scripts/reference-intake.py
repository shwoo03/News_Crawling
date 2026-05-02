#!/usr/bin/env python3
"""Analyze external references before implementation.

The script is intentionally review-first. It can inspect an already-cloned
repository, draft a candidate card, and plan a safe clone path. Actual network
clone requires --apply and always lands under runtime/external-repos/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


TEXT_EXTENSIONS = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml", ".sh"}
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "NOTICE")


@dataclass
class ReferenceAnalysis:
    name: str
    local_path: str
    checked_revision: str
    license: str
    has_readme: bool
    has_docs: bool
    has_tests: bool
    package_files: list[str] = field(default_factory=list)
    top_level_dirs: list[str] = field(default_factory=list)
    notable_files: list[str] = field(default_factory=list)
    module_inventory: list[str] = field(default_factory=list)
    reusable_units: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_inside(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    resolved.relative_to(root.resolve(strict=False))
    return resolved


def relative_or_abs(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def run_git(path: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
    except subprocess.SubprocessError:
        return "not checked"
    if result.returncode != 0:
        return "not checked"
    return result.stdout.strip() or "not checked"


def detect_license(path: Path) -> str:
    for name in LICENSE_NAMES:
        candidate = path / name
        if candidate.is_file():
            first_lines = "\n".join(candidate.read_text(encoding="utf-8", errors="replace").splitlines()[:20])
            lowered = first_lines.lower()
            if "mit license" in lowered:
                return "MIT"
            if "apache license" in lowered:
                return "Apache"
            if "gnu general public license" in lowered or "gpl" in lowered:
                return "GPL"
            if "bsd" in lowered:
                return "BSD"
            return name
    return "not found"


def has_any(path: Path, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if any(path.glob(pattern)):
            return True
    return False


def count_text_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def cache_path(root: Path) -> Path:
    return root / "runtime" / "reference-intake-cache.jsonl"


def text_files(path: Path) -> list[Path]:
    files: list[Path] = []
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in TEXT_EXTENSIONS:
            parts = set(item.relative_to(path).parts)
            if {".git", "node_modules", "__pycache__", ".venv", "venv"} & parts:
                continue
            files.append(item)
    return sorted(files)


def source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(str(path.resolve(strict=False)).encode("utf-8"))
    head = run_git(path, ["rev-parse", "HEAD"]) if (path / ".git").exists() else "not checked"
    if head != "not checked":
        status = run_git(path, ["status", "--short"])
        digest.update(f"git:{head}\nstatus:{status}".encode("utf-8"))
        return digest.hexdigest()
    for item in text_files(path)[:500]:
        try:
            relative = item.relative_to(path).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(item.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()


def read_cache(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = cache_path(root)
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    findings: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} record must be an object")
            continue
        records.append(value)
    return records, findings


def cached_analysis(root: Path, target: Path, fingerprint: str) -> ReferenceAnalysis | None:
    records, _findings = read_cache(root)
    local_path = target.resolve(strict=False).as_posix()
    for record in reversed(records):
        if record.get("local_path") != local_path or record.get("source_hash") != fingerprint:
            continue
        analysis = record.get("analysis")
        if isinstance(analysis, dict):
            allowed = {field.name for field in ReferenceAnalysis.__dataclass_fields__.values()}
            payload = {key: analysis.get(key) for key in allowed}
            for key in ("package_files", "top_level_dirs", "notable_files", "module_inventory", "reusable_units", "risk_notes", "sources"):
                if not isinstance(payload.get(key), list):
                    payload[key] = []
            return ReferenceAnalysis(**payload)
    return None


def append_cache(root: Path, target: Path, fingerprint: str, analysis: ReferenceAnalysis) -> None:
    path = cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": utc_now(),
        "local_path": target.resolve(strict=False).as_posix(),
        "source_hash": fingerprint,
        "analysis": asdict(analysis),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def get_analysis(root: Path, target: Path, *, refresh: bool = False, write_cache: bool = False) -> tuple[ReferenceAnalysis, str, str]:
    fingerprint = source_hash(target)
    if not refresh:
        cached = cached_analysis(root, target, fingerprint)
        if cached:
            return cached, fingerprint, "hit"
    analysis = analyze_local(target)
    if write_cache:
        append_cache(root, target, fingerprint, analysis)
    return analysis, fingerprint, "refresh" if refresh else "miss"


def analyze_local(path: Path) -> ReferenceAnalysis:
    package_files = [
        rel.as_posix()
        for rel in (Path("package.json"), Path("pyproject.toml"), Path("requirements.txt"), Path("Cargo.toml"), Path("go.mod"), Path("pnpm-workspace.yaml"))
        if (path / rel).is_file()
    ]
    top_dirs = sorted(item.name for item in path.iterdir() if item.is_dir() and not item.name.startswith("."))
    notable = []
    for rel in ("README.md", "AGENTS.md", "CLAUDE.md", "docs", "scripts", "skills", "agents", "tests"):
        if (path / rel).exists():
            notable.append(rel)
    module_inventory: list[str] = []
    reusable_units: list[str] = []
    for directory in top_dirs[:24]:
        dir_path = path / directory
        files = [item for item in dir_path.rglob("*") if item.is_file() and item.suffix.lower() in TEXT_EXTENSIONS]
        module_inventory.append(f"{directory}: {len(files)} text file(s)")
        if files and directory in {"scripts", "skills", "agents", "docs", "rules", "tests", "packages", "src"}:
            reusable_units.append(directory)
    risks: list[str] = []
    if not package_files:
        risks.append("No package/dependency manifest detected.")
    if not has_any(path, ("**/test*", "**/*test*", "tests", "__tests__")):
        risks.append("No obvious test surface detected.")
    if detect_license(path) == "not found":
        risks.append("No license file detected.")
    sources = build_sources(path)
    return ReferenceAnalysis(
        name=path.name,
        local_path=path.as_posix(),
        checked_revision=run_git(path, ["rev-parse", "HEAD"]),
        license=detect_license(path),
        has_readme=has_any(path, ("README*",)),
        has_docs=(path / "docs").is_dir() or (path / "doc").is_dir(),
        has_tests=has_any(path, ("tests", "__tests__", "**/*test*", "**/test*")),
        package_files=package_files,
        top_level_dirs=top_dirs,
        notable_files=notable,
        module_inventory=module_inventory,
        reusable_units=reusable_units,
        risk_notes=risks,
        sources=sources,
    )


def file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return "unreadable"


def source_item(root: Path, rel: str, kind: str, evidence: str) -> dict[str, str]:
    path = root / rel
    return {
        "path": rel,
        "kind": kind,
        "evidence": evidence,
        "hash_or_line_ref": file_hash(path) if path.is_file() else "directory",
    }


def build_sources(path: Path) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for rel, kind, evidence in (
        ("README.md", "readme", "Project overview and reuse intent signal."),
        ("LICENSE", "license", "License and redistribution boundary signal."),
        ("pyproject.toml", "package_manifest", "Python package/dependency signal."),
        ("package.json", "package_manifest", "JavaScript package/dependency signal."),
        ("requirements.txt", "package_manifest", "Python dependency signal."),
        ("Cargo.toml", "package_manifest", "Rust package/dependency signal."),
        ("go.mod", "package_manifest", "Go module/dependency signal."),
        ("scripts", "module_dir", "Script surface that may contain reusable automation."),
        ("src", "module_dir", "Source module surface for structure review."),
        ("tests", "test_dir", "Validation surface signal."),
        ("docs", "docs_dir", "Documentation surface signal."),
    ):
        if (path / rel).exists():
            sources.append(source_item(path, rel, kind, evidence))
    if not sources:
        sources.append({"path": ".", "kind": "repository", "evidence": "Repository root inspected.", "hash_or_line_ref": source_hash(path)[:16]})
    return sources[:12]


def render_sources(sources: list[dict[str, str]]) -> str:
    return "\n".join(
        "  - "
        + json.dumps(
            {
                "path": item.get("path", ""),
                "kind": item.get("kind", ""),
                "evidence": item.get("evidence", ""),
                "hash_or_line_ref": item.get("hash_or_line_ref", ""),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for item in sources
    )


def slugify(value: str) -> str:
    lowered = value.lower().replace(".git", "")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "reference"


def external_clone_path(root: Path, url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) >= 2:
            owner = slugify(parts[-2])
            repo = slugify(parts[-1])
            return root / "runtime" / "external-repos" / host / f"{owner}__{repo}"
        return root / "runtime" / "external-repos" / host / slugify(parts[-1] if parts else "repo")
    source = Path(url)
    return root / "runtime" / "external-repos" / "local" / slugify(source.name)


def render_candidate_card(analysis: ReferenceAnalysis, *, url: str, searched_for: str, reviewer: str, reference_task_id: str = "") -> str:
    useful = analysis.reusable_units or analysis.notable_files or ["repository structure requires manual review"]
    score_fit = 15 if analysis.has_readme else 10
    score_structure = 12 if analysis.module_inventory else 8
    score_validation = 15 if analysis.has_tests else 5
    score_maint = 10 if analysis.checked_revision != "not checked" else 5
    score_absorb = 12 if analysis.reusable_units else 7
    score_risk = 8 if analysis.license != "not found" else 4
    score_explain = 8 if analysis.has_docs or analysis.has_readme else 4
    total = score_fit + score_structure + score_validation + score_maint + score_absorb + score_risk + score_explain
    module_lines = "\n".join(f"  - {item}" for item in analysis.module_inventory[:20]) or "  - manual inventory required"
    reusable_lines = "\n".join(f"  - {item}" for item in useful[:12])
    not_to_copy = "  - Do not copy the repository wholesale before proposal approval."
    risks = "; ".join(analysis.risk_notes) if analysis.risk_notes else "No immediate local-analysis risk found."
    source_lines = render_sources(analysis.sources)
    return f"""# {analysis.name}

## 기본 정보

- `name`: {analysis.name}
- `url`: {url or analysis.local_path}
- `source_type`: repository
- `status`: reviewing
- `searched_for`: {searched_for or 'local reference analysis'}
- `created_at`: {utc_today()}
- `reviewed_at`: {utc_today()}
- `reviewer`: {reviewer}
- `query_provenance`: {searched_for or 'not provided'}
- `candidate_rank`: not ranked
- `candidate_count`: not ranked
- `reference_task_id`: {reference_task_id or 'not queued'}

## 왜 보는가

- `problem_statement`: Find reusable OSS/reference patterns before direct implementation.
- `why_it_matters`: The project should prioritize dependency, wrapper, partial_copy, or concept_only reuse before custom code.
- `expected_value`: Identify modular pieces and governance requirements for safe absorption.

## 유용한 패턴

- `useful_patterns`:
{reusable_lines}
- `what_to_copy_conceptually`:
{reusable_lines}
- `what_to_copy_directly`:
  - none before user approval
- `what_not_to_copy`:
{not_to_copy}

## 구조 분석

- `module_inventory`:
{module_lines}
- `reusable_units`:
{reusable_lines}

## 증거

- `evidence_summary`: README={analysis.has_readme}; docs={analysis.has_docs}; tests={analysis.has_tests}; manifests={', '.join(analysis.package_files) if analysis.package_files else 'none'}
- `local_clone_path`: {analysis.local_path}
- `checked_revision`: {analysis.checked_revision}
- `freshness_signal`: checked revision recorded locally; remote freshness requires separate review
- `maintenance_signal`: package files: {', '.join(analysis.package_files) if analysis.package_files else 'none detected'}
- `documentation_signal`: README={analysis.has_readme}; docs={analysis.has_docs}
- `validation_signal`: tests={analysis.has_tests}
- `sources`:
{source_lines}

## 리스크

- `license`: {analysis.license}
- `security_or_privacy_risk`: {risks}
- `maintenance_risk`: remote issue/release health not checked by local analysis
- `complexity_risk`: top-level directories: {len(analysis.top_level_dirs)}
- `dependency_risk`: package manifests: {', '.join(analysis.package_files) if analysis.package_files else 'none detected'}
- `fit_risk`: requires proposal review before absorption

## 적용 후보

- `applies_to`: docs | rules | skills | scripts | tests | runtime | other
- `target_files_or_areas`:
  - TBD after user review
- `adoption_decision`: adapt
- `absorption_mode`: concept_only
- `direct_implementation_reason`: not applicable; reuse paths still under review
- `decision_reason`: Local analysis found reusable units, but approval is required before absorption.
- `next_action`: create reference adoption proposal if user approves this candidate

## 점수

| 기준 | 배점 | 점수 | 근거 |
| --- | ---: | ---: | --- |
| 문제 적합성 | 20 | {score_fit} | OSS-first reuse candidate |
| 구조 명확성 | 15 | {score_structure} | module inventory generated |
| 검증 가능성 | 15 | {score_validation} | tests detected: {analysis.has_tests} |
| 유지보수 신호 | 15 | {score_maint} | checked revision: {analysis.checked_revision} |
| 흡수 비용 | 15 | {score_absorb} | reusable units: {', '.join(useful[:5])} |
| 보안/라이선스 리스크 | 10 | {score_risk} | license: {analysis.license} |
| 설명 가치 | 10 | {score_explain} | README/docs present |
| 합계 | 100 | {total} | generated by scripts/reference-intake.py |

## Dry-Run 제안

- `proposal_needed`: yes
- `files_to_change`:
  - runtime/proposals/reference-adoption/
- `behavior_change`: Require modular absorption review before direct implementation.
- `validation_plan`: python scripts/validate-reference-candidates.py && python scripts/validate-reference-proposals.py
- `rollback_or_stop_condition`: Stop if approval is missing, source provenance is unclear, or copy boundary cannot be stated.
- `approval_required`: yes
- `copy_boundary`: not applicable

## 최종 기록

- `final_status`: reviewing
- `implemented_in`:
  - not implemented
- `validation_result`: not run
- `activity_log_entry`: not recorded
- `notes`: generated from local analysis; verify remote metadata before adoption
"""


def cmd_analyze(root: Path, args: argparse.Namespace) -> int:
    target = resolve_inside(root, args.local_path) if args.local_path else Path(args.path).resolve()
    if not target.is_dir():
        print(f"local path not a directory: {target}", file=sys.stderr)
        return 2
    analysis, fingerprint, cache_status = get_analysis(root, target, refresh=args.refresh, write_cache=args.cache)
    if args.format == "json":
        print(json.dumps({**asdict(analysis), "source_hash": fingerprint, "cache_status": cache_status}, ensure_ascii=False, indent=2))
    else:
        print(f"Reference Analysis: {analysis.name}")
        print(f"revision: {analysis.checked_revision}")
        print(f"license: {analysis.license}")
        print(f"cache_status: {cache_status}")
        print(f"readme/docs/tests: {analysis.has_readme}/{analysis.has_docs}/{analysis.has_tests}")
        print("reusable_units: " + (", ".join(analysis.reusable_units) if analysis.reusable_units else "(none detected)"))
    return 0


def cmd_card_draft(root: Path, args: argparse.Namespace) -> int:
    target = resolve_inside(root, args.local_path) if args.local_path else Path(args.path).resolve()
    if not target.is_dir():
        print(f"local path not a directory: {target}", file=sys.stderr)
        return 2
    analysis, _fingerprint, _cache_status = get_analysis(root, target, refresh=args.refresh, write_cache=args.write or args.cache)
    body = render_candidate_card(analysis, url=args.url, searched_for=args.searched_for, reviewer=args.reviewer, reference_task_id=args.reference_task_id)
    output = root / "research" / "reference-candidates" / f"{utc_today()}-{slugify(args.name or analysis.name)}.md"
    if args.output:
        output = resolve_inside(root, args.output)
    if args.write:
        if output.exists():
            print(f"refusing to overwrite existing candidate card: {output}", file=sys.stderr)
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"created {output.relative_to(root).as_posix()}")
    else:
        print(f"# suggested_output: {output.relative_to(root).as_posix()}")
        print(body)
    return 0


def cmd_clone(root: Path, args: argparse.Namespace) -> int:
    destination = resolve_inside(root, args.destination) if args.destination else external_clone_path(root, args.url)
    allowed_root = (root / "runtime" / "external-repos").resolve(strict=False)
    try:
        destination.resolve(strict=False).relative_to(allowed_root)
    except ValueError:
        print(f"clone destination must stay under runtime/external-repos: {destination}", file=sys.stderr)
        return 2
    if destination.exists():
        print(f"clone destination already exists: {destination}", file=sys.stderr)
        return 1
    command = ["git", "clone", "--depth", "1", args.url, str(destination)]
    if not args.apply:
        payload = {"dry_run": True, "command": command, "destination": destination.relative_to(root).as_posix()}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else " ".join(command))
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, cwd=str(root), capture_output=True, text=True, encoding="utf-8", timeout=args.timeout)
    if result.returncode != 0:
        print((result.stderr or result.stdout).strip(), file=sys.stderr)
        return result.returncode
    print(f"cloned {args.url} -> {destination.relative_to(root).as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze an already cloned local reference.")
    analyze.add_argument("path", nargs="?", default=".")
    analyze.add_argument("--local-path", default="", help="Path inside the project root to analyze.")
    analyze.add_argument("--format", choices=("text", "json"), default="text")
    analyze.add_argument("--cache", action="store_true", help="Append the analysis to runtime/reference-intake-cache.jsonl.")
    analyze.add_argument("--refresh", action="store_true", help="Ignore matching cached analysis.")
    analyze.set_defaults(func=cmd_analyze)

    card = sub.add_parser("card-draft", help="Draft a reference candidate card from local analysis.")
    card.add_argument("path", nargs="?", default=".")
    card.add_argument("--local-path", default="", help="Path inside the project root to analyze.")
    card.add_argument("--url", default="")
    card.add_argument("--searched-for", default="")
    card.add_argument("--reviewer", default="codex")
    card.add_argument("--reference-task-id", default="")
    card.add_argument("--name", default="")
    card.add_argument("--output", default="")
    card.add_argument("--write", action="store_true")
    card.add_argument("--cache", action="store_true", help="Append the analysis cache even when not writing the card.")
    card.add_argument("--refresh", action="store_true", help="Ignore matching cached analysis.")
    card.set_defaults(func=cmd_card_draft)

    clone = sub.add_parser("clone", help="Plan or run a safe clone into runtime/external-repos.")
    clone.add_argument("--url", required=True)
    clone.add_argument("--destination", default="")
    clone.add_argument("--apply", action="store_true", help="Actually run git clone. Default is dry-run.")
    clone.add_argument("--timeout", type=int, default=60)
    clone.add_argument("--format", choices=("text", "json"), default="text")
    clone.set_defaults(func=cmd_clone)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    return args.func(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
