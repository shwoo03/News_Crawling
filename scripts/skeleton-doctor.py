#!/usr/bin/env python3
"""Diagnose whether a skeleton-based project is ready to operate.

This is a read-only operator diagnostic. It does not replace
verify-skeleton.py; it wraps structural checks with higher-level readiness
signals for project startup, reference review, runtime startup, logging, and
handoff continuity.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


PROFILE_CORE_FIELDS = ("primary_goal", "success_criteria", "failure_definition")
REQUIRED_OPERATING_DOCS = (
    "AGENTS.md",
    "docs/PROJECT_PROFILE.md",
    "docs/OPERATING_LOOP.md",
    "docs/SESSION_CONTINUITY.md",
    "rules/common/README.md",
)
REFERENCE_SURFACE = (
    "docs/REFERENCE_DISCOVERY_WORKFLOW.md",
    "docs/REFERENCE_REVIEW.template.md",
    "research/reference-candidates/README.md",
    "runtime/proposals/reference-adoption/README.md",
    "scripts/quality-gate.py",
    "scripts/validate-reference-candidates.py",
    "scripts/validate-reference-proposals.py",
)
RUNTIME_STARTUP_SURFACE = (
    "docs/RUNTIME_STARTUP.template.md",
    "runtime/state/session-handoff.md",
    "runtime/activity-log.jsonl",
    "runtime/review-queue.jsonl",
)
FIELD_RE = re.compile(r"^-\s+`([^`]+)`:\s*(.*)$", re.MULTILINE)


@dataclass
class Check:
    section: str
    status: str
    name: str
    detail: str
    next_action: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_blank(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return (
        stripped == ""
        or stripped in {"-", "TBD", "todo", "TODO"}
        or stripped.startswith("[NEEDS CLARIFICATION:")
    )


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def add(
    checks: list[Check],
    section: str,
    status: str,
    name: str,
    detail: str,
    next_action: str = "",
) -> None:
    checks.append(Check(section, status, name, detail, next_action))


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_python(script: Path, args: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=command_env(),
        timeout=120,
    )


def parse_profile_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return {match.group(1): match.group(2).strip() for match in FIELD_RE.finditer(text)}


def check_operating_contract(root: Path, checks: list[Check]) -> None:
    missing = [path for path in REQUIRED_OPERATING_DOCS if not (root / path).exists()]
    if missing:
        add(
            checks,
            "Operating Contract",
            "FAIL",
            "required operating docs",
            "missing: " + ", ".join(missing),
            "restore missing files from the skeleton or run the safe upgrade workflow",
        )
    else:
        add(checks, "Operating Contract", "OK", "required operating docs", "all required docs exist")

    fields = parse_profile_fields(root / "docs" / "PROJECT_PROFILE.md")
    missing_fields = [field for field in PROFILE_CORE_FIELDS if is_blank(fields.get(field))]
    if missing_fields:
        add(
            checks,
            "Operating Contract",
            "FAIL",
            "project profile core fields",
            "blank or missing: " + ", ".join(missing_fields),
            "answer the profile questions in docs/PROJECT_PROFILE.template.md",
        )
    else:
        add(
            checks,
            "Operating Contract",
            "OK",
            "project profile core fields",
            "primary_goal, success_criteria, and failure_definition are filled",
        )


def check_reference_surface(root: Path, checks: list[Check]) -> None:
    missing = [path for path in REFERENCE_SURFACE if not (root / path).exists()]
    if missing:
        add(
            checks,
            "Reference Review",
            "FAIL",
            "reference workflow surface",
            "missing: " + ", ".join(missing),
            "restore reference workflow files from the skeleton",
        )
    else:
        add(
            checks,
            "Reference Review",
            "OK",
            "reference workflow surface",
            "candidate cards, proposal docs, and validators exist",
        )

    candidate_script = root / "scripts" / "validate-reference-candidates.py"
    if candidate_script.exists():
        result = run_python(candidate_script, ["--root", str(root)], root)
        status = "OK" if result.returncode == 0 else "FAIL"
        detail = first_output_line(result) or f"exit {result.returncode}"
        add(
            checks,
            "Reference Review",
            status,
            "candidate cards",
            detail,
            "" if status == "OK" else "fix research/reference-candidates/*.md and rerun validator",
        )

    proposal_script = root / "scripts" / "validate-reference-proposals.py"
    if proposal_script.exists():
        result = run_python(proposal_script, ["--root", str(root)], root)
        status = "OK" if result.returncode == 0 else "FAIL"
        detail = first_output_line(result) or f"exit {result.returncode}"
        add(
            checks,
            "Reference Review",
            status,
            "reference adoption proposals",
            detail,
            "" if status == "OK" else "fix runtime/proposals/reference-adoption/*.md and rerun validator",
        )

    concrete_review = root / "docs" / "REFERENCE_REVIEW.md"
    if concrete_review.exists():
        add(checks, "Reference Review", "OK", "project reference review", "docs/REFERENCE_REVIEW.md exists")
    else:
        add(
            checks,
            "Reference Review",
            "INFO",
            "project reference review",
            "no concrete docs/REFERENCE_REVIEW.md found",
            "instantiate docs/REFERENCE_REVIEW.template.md when a project goal is clear",
        )


def check_runtime_startup(root: Path, checks: list[Check]) -> None:
    missing = [path for path in RUNTIME_STARTUP_SURFACE if not (root / path).exists()]
    if missing:
        add(
            checks,
            "Runtime Startup",
            "FAIL",
            "startup and continuity surface",
            "missing: " + ", ".join(missing),
            "restore missing runtime startup or continuity files",
        )
    else:
        add(
            checks,
            "Runtime Startup",
            "OK",
            "startup and continuity surface",
            "runtime startup template, activity log, and handoff file exist",
        )

    concrete_startup = root / "docs" / "RUNTIME_STARTUP.md"
    if concrete_startup.exists():
        add(checks, "Runtime Startup", "OK", "project startup contract", "docs/RUNTIME_STARTUP.md exists")
    else:
        add(
            checks,
            "Runtime Startup",
            "INFO",
            "project startup contract",
            "no concrete docs/RUNTIME_STARTUP.md found",
            "instantiate docs/RUNTIME_STARTUP.template.md when startup commands are known",
        )

    handoff = root / "runtime" / "state" / "session-handoff.md"
    if handoff.exists() and handoff.stat().st_size > 0:
        add(checks, "Runtime Startup", "OK", "session handoff", "handoff file is present and non-empty")
    elif handoff.exists():
        add(checks, "Runtime Startup", "WARN", "session handoff", "handoff file exists but is empty")

    for jsonl in ("runtime/activity-log.jsonl", "runtime/agent-runs.jsonl", "runtime/review-queue.jsonl"):
        path = root / jsonl
        if path.exists():
            errors = parse_jsonl_errors(path)
            if errors:
                add(
                    checks,
                    "Runtime Startup",
                    "FAIL",
                    jsonl,
                    errors[0],
                    "fix or rotate the invalid JSONL line before relying on runtime state",
                )
            else:
                add(checks, "Runtime Startup", "OK", jsonl, "JSONL parses")


def parse_jsonl_errors(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        return [f"could not read {path}: {exc}"]
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.as_posix()}:{line_no} invalid JSON: {exc}")
            break
    return errors


def check_validation(root: Path, checks: list[Check], *, full_verify: bool) -> None:
    verify = root / "scripts" / "verify-skeleton.py"
    if not verify.exists():
        add(
            checks,
            "Validation",
            "FAIL",
            "verify-skeleton",
            "scripts/verify-skeleton.py missing",
            "restore the verifier from the skeleton",
        )
        return
    args = ["--root", str(root)]
    if not full_verify:
        args.append("--skip-wiki-lint")
    result = run_python(verify, args, root)
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        status = "FAIL"
    elif "WARN" in output or "skeleton findings:" in output:
        status = "WARN"
    else:
        status = "OK"
    add(
        checks,
        "Validation",
        status,
        "verify-skeleton",
        first_output_line(result) or f"exit {result.returncode}",
        "" if status == "OK" else "review verify-skeleton output and remove temporary artifacts if needed",
    )

    open_questions = root / "scripts" / "list-open-questions.py"
    if open_questions.exists():
        result = run_python(open_questions, ["--root", str(root), "--count"], root)
        if result.returncode != 0:
            add(checks, "Validation", "WARN", "open questions", "could not count open questions")
            return
        count_text = (result.stdout or "").strip()
        try:
            count = int(count_text)
        except ValueError:
            add(checks, "Validation", "WARN", "open questions", f"unexpected output: {count_text!r}")
            return
        if count:
            add(
                checks,
                "Validation",
                "WARN",
                "open questions",
                f"{count} NEEDS CLARIFICATION marker(s)",
                "run python scripts/list-open-questions.py",
            )
        else:
            add(checks, "Validation", "OK", "open questions", "0 open questions")

    review_queue = root / "scripts" / "review-queue.py"
    if review_queue.exists():
        result = run_python(review_queue, ["--root", str(root), "count"], root)
        if result.returncode not in {0, 1}:
            add(checks, "Validation", "WARN", "human review queue", "could not count review items")
            return
        count_text = (result.stdout or "").strip()
        try:
            count = int(count_text)
        except ValueError:
            add(checks, "Validation", "WARN", "human review queue", f"unexpected output: {count_text!r}")
            return
        if count:
            add(
                checks,
                "Validation",
                "WARN",
                "human review queue",
                f"{count} unresolved review item(s)",
                "run python scripts/review-queue.py list",
            )
        else:
            add(checks, "Validation", "OK", "human review queue", "0 unresolved review items")


def check_projects_root(root: Path, projects_root: Path, checks: list[Check]) -> None:
    script = root / "scripts" / "upgrade-from-skeleton.py"
    if not script.exists():
        add(
            checks,
            "Project Propagation",
            "WARN",
            "upgrade planner",
            "scripts/upgrade-from-skeleton.py missing",
        )
        return
    if not projects_root.is_dir():
        add(
            checks,
            "Project Propagation",
            "WARN",
            "projects root",
            f"not a directory: {projects_root}",
        )
        return
    result = run_python(script, ["--projects-root", str(projects_root), "--json"], root)
    if result.returncode != 0:
        add(
            checks,
            "Project Propagation",
            "WARN",
            "upgrade planner",
            first_output_line(result) or f"exit {result.returncode}",
        )
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        add(checks, "Project Propagation", "WARN", "upgrade planner", f"invalid JSON: {exc}")
        return
    actions = payload.get("actions", [])
    summary = Counter(f"{item.get('action')}:{item.get('safety')}" for item in actions if isinstance(item, dict))
    safe_adds = summary.get("add:safe", 0)
    risky_updates = summary.get("update_available:risky", 0)
    if safe_adds:
        add(
            checks,
            "Project Propagation",
            "WARN",
            "safe missing updates",
            f"{safe_adds} safe file(s) can be added to existing projects",
            "run upgrade-from-skeleton.py --projects-root ... --apply --safe-only",
        )
    else:
        add(checks, "Project Propagation", "OK", "safe missing updates", "no add:safe items")
    if risky_updates:
        add(
            checks,
            "Project Propagation",
            "INFO",
            "risky updates",
            f"{risky_updates} project-owned or changed file(s) need manual review",
        )


def first_output_line(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stdout or result.stderr or "").strip()
    if not text:
        return ""
    return text.splitlines()[0]


def render_text(root: Path, checks: list[Check]) -> str:
    counts = Counter(check.status for check in checks)
    lines = [
        "Skeleton Doctor",
        f"root: {root}",
        f"summary: {counts.get('FAIL', 0)} fail, {counts.get('WARN', 0)} warn, {counts.get('OK', 0)} ok, {counts.get('INFO', 0)} info",
    ]
    current_section = ""
    for check in checks:
        if check.section != current_section:
            current_section = check.section
            lines.append("")
            lines.append(f"[{current_section}]")
        lines.append(f"  {check.status:<4} {check.name}: {check.detail}")
        if check.next_action:
            lines.append(f"       next: {check.next_action}")
    return "\n".join(lines)


def render_json(root: Path, checks: list[Check]) -> str:
    counts = Counter(check.status for check in checks)
    payload = {
        "root": str(root),
        "summary": dict(sorted(counts.items())),
        "checks": [asdict(check) for check in checks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root to diagnose (default: skeleton root).")
    parser.add_argument(
        "--projects-root",
        default=None,
        help="Optional parent directory of existing projects to check with upgrade-from-skeleton.py.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--full-verify",
        action="store_true",
        help="Run verify-skeleton.py with wiki-lint instead of the faster structural pass.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2

    checks: list[Check] = []
    check_operating_contract(root, checks)
    check_reference_surface(root, checks)
    check_runtime_startup(root, checks)
    check_validation(root, checks, full_verify=args.full_verify)
    if args.projects_root:
        check_projects_root(root, Path(args.projects_root).resolve(), checks)

    if args.format == "json":
        print(render_json(root, checks))
    else:
        print(render_text(root, checks))

    return 1 if any(check.status == "FAIL" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
