#!/usr/bin/env python3
"""Create a new project from the reusable AI architecture skeleton.

The destination is a self-contained copy of this skeleton with
project-specific identity seeded and skeleton-internal artifacts stripped.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# Ensure Korean next-step guidance prints cleanly on Windows consoles that
# default to cp949 / cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


# Directories skipped by name anywhere in the tree.
SKIP_DIRS = {
    ".git",
    ".codex",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
}

# Individual files skipped by their path relative to the skeleton root.
# These carry skeleton-internal history that must not leak into a new project.
SKIP_FILES = {
    "runtime/activity-log.jsonl",
    "runtime/agent-runs.jsonl",
    "runtime/install-state.jsonl",
    "runtime/skill-usage.jsonl",
    "runtime/skill-lifecycle.jsonl",
    "runtime/session-snapshot.json",
    "runtime/review-queue.jsonl",
    "runtime/reference-tasks.jsonl",
    "runtime/checkpoints.jsonl",
    "runtime/state/session-handoff.md",
    "knowledge/index.md",
    "knowledge/log.md",
    "knowledge/project-registry.md",
    "knowledge/lint-report.md",
    ".claude/settings.local.json",
}

# File basenames skipped anywhere in the tree.
SKIP_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

# Name prefixes skipped anywhere in the tree. Catches transient debug/scratch
# files or directories (e.g. runtime/tmp-regex2.py, runtime/tmp-tests/) that the
# skeleton author may leave behind but that must never leak into a fresh project.
SKIP_NAME_PREFIXES = (
    "tmp-",
    "scratch-",
)
SKIP_NAME_CONTAINS = (
    "-smoke-",
)
PRESERVE_IN_EXTERNAL_REPOS = {"README.md", ".gitkeep"}
# Directories copied as empty shells (preserve structure, drop accumulated content).
# README.md and .gitkeep inside these are preserved.
EMPTY_EXCEPT_DOCS = {
    "runtime/external-repos",
    "runtime/proposals",
    "runtime/validation",
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _inline_list(value: str) -> list[str]:
    return [item.strip().strip('"').strip("'") for item in value.split(",") if item.strip()]


def load_install_profiles(root: Path) -> tuple[str, dict[str, list[str]]]:
    path = root / "config" / "install-profiles.yaml"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    default_match = re.search(r"^default_profile:\s*([^\n#]+)", text, re.MULTILINE)
    default = default_match.group(1).strip().strip('"').strip("'") if default_match else "full-canonical"
    profiles: dict[str, list[str]] = {}
    profile_block = re.search(r"^profiles:\s*$", text, re.MULTILINE)
    if profile_block:
        tail = text[profile_block.end() :]
        for match in re.finditer(r"^\s{2}([A-Za-z0-9_-]+):\s*\n(.*?)(?=^\s{2}[A-Za-z0-9_-]+:\s*$|\Z)", tail, re.MULTILINE | re.DOTALL):
            components_match = re.search(r"components:\s*\[([^\]]*)\]", match.group(2))
            profiles[match.group(1)] = _inline_list(components_match.group(1)) if components_match else []
    if not profiles:
        profiles = {"full-canonical": ["core", "validation", "runtime", "reference", "wiki", "skills", "agents", "docs", "bootstrap"]}
    if default not in profiles:
        default = "full-canonical" if "full-canonical" in profiles else sorted(profiles)[0]
    return default, profiles


def is_relative_to(path: Path, parent: Path) -> bool:
    # Python 3.9+ has Path.is_relative_to. We keep this wrapper because the
    # rest of this script treats "inside target" as a boolean check rather
    # than an exception boundary. All skeleton scripts require Python 3.9+.
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def should_skip(path: Path, source: Path, target: Path) -> bool:
    rel = path.relative_to(source).as_posix()
    if rel.startswith("runtime/external-repos/"):
        return not (
            Path(rel).parent.as_posix() == "runtime/external-repos"
            and path.name in PRESERVE_IN_EXTERNAL_REPOS
        )
    if rel == "docs/_meta" or rel.startswith("docs/_meta/"):
        return True
    if path.name in SKIP_DIRS:
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if path.name.startswith(SKIP_NAME_PREFIXES):
        return True
    if any(fragment in path.name for fragment in SKIP_NAME_CONTAINS):
        return True
    if rel in SKIP_FILES:
        return True
    if path == target or is_relative_to(path, target):
        return True
    # Refuse to copy symlinks out of the skeleton. shutil.copytree defaults to
    # symlinks=False which dereferences links and copies their target content.
    # That would let a symlink planted in the skeleton (e.g. pointing to
    # /etc/passwd or C:\Windows\System32\...) smuggle external content into the
    # new project. The skeleton has no legitimate symlinks, so skipping them is
    # safe and fails-closed.
    if path.is_symlink():
        return True
    return False


def copy_skeleton(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if should_skip(item, source, target):
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                destination,
                dirs_exist_ok=True,
                symlinks=True,  # preserve links rather than dereference; should_skip
                                # additionally filters out any symlinks it sees.
                ignore=lambda current, names: {
                    name
                    for name in names
                    if should_skip(Path(current) / name, source, target)
                },
            )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def empty_accumulated_dirs(target: Path) -> None:
    """Strip accumulated content from directories that should start empty in a new
    project. Keeps README.md and .gitkeep."""
    preserved_names = {"README.md", ".gitkeep", "_template.md"}
    for rel in EMPTY_EXCEPT_DOCS:
        directory = target / rel
        if not directory.exists():
            continue
        for entry in sorted(directory.rglob("*"), reverse=True):
            if rel == "runtime/external-repos":
                if entry.parent == directory and entry.name in preserved_names:
                    continue
            elif entry.name in preserved_names:
                continue
            if entry.is_dir():
                try:
                    next(entry.iterdir())
                except StopIteration:
                    entry.rmdir()
            else:
                entry.unlink()


def seed_project_profile(
    target: Path,
    source: Path,
    name: str,
    domain: str,
    stack: str,
    owner: str,
) -> None:
    """Produce docs/PROJECT_PROFILE.md by instantiating the single template so
    there is only one source of truth for the profile schema.

    The template's meta-instruction sections (prose describing how to use the
    template) are stripped so they do not appear in the seeded, already-
    instantiated file. Only factual schema sections are kept.
    """
    template_path = source / "docs" / "PROJECT_PROFILE.template.md"
    if not template_path.exists():
        raise SystemExit(
            f"template missing: {template_path}. Cannot seed PROJECT_PROFILE.md"
        )
    template = template_path.read_text(encoding="utf-8")

    # Keep only the factual schema sections. Meta-instruction sections explain
    # the template itself ("무엇을 하는가", "왜 필요한가", etc.) and should not
    # appear in an instantiated project profile where they would clutter the
    # project's actual facts. "Agent Fill-In Contract" is dropped because it
    # contains example `[NEEDS CLARIFICATION: ...]` lines that otherwise appear
    # as real outstanding questions. "활성 운영 선택" is kept but its
    # explanatory paragraph stripped to match the factual tone.
    KEEP_HEADINGS = {
        "## 기본 정보",
        "## 목표",
        "## 프로젝트별 맥락",
        "## 활성 운영 선택 (선택 — 에이전트가 나중에 채움)",
        "## 첫 반복 체크리스트",
    }
    lines = template.splitlines()
    kept_sections: list[list[str]] = []
    current: list[str] | None = None
    keeping = False
    for line in lines:
        if line.startswith("## "):
            # section boundary
            stripped = line.strip()
            if stripped in KEEP_HEADINGS:
                keeping = True
                current = [line]
                kept_sections.append(current)
            else:
                keeping = False
                current = None
            continue
        if keeping and current is not None:
            current.append(line)

    if not kept_sections:
        raise SystemExit(
            "PROJECT_PROFILE.template.md structure drift: none of the expected "
            "factual sections were found. Update either the template or "
            "scripts/bootstrap/new-project.py."
        )

    # Strip the explanatory paragraph inside "활성 운영 선택" (everything before
    # the first bullet list). The section header is kept but the prose that
    # explains what the section is *for* is template documentation, not
    # project facts.
    for section in kept_sections:
        first_bullet_idx = next(
            (i for i, ln in enumerate(section) if ln.lstrip().startswith("- ")),
            None,
        )
        if first_bullet_idx is None or first_bullet_idx <= 1:
            continue
        # Keep header (index 0), drop intermediate prose, keep from first bullet.
        del section[1:first_bullet_idx]

    # Re-join sections with a blank line between them and a blank line after
    # each heading.
    rendered_sections: list[str] = []
    for section in kept_sections:
        # Ensure blank line after heading.
        if len(section) >= 2 and section[1].strip() != "":
            section = [section[0], ""] + section[1:]
        rendered_sections.append("\n".join(section).rstrip())
    schema_body = "\n\n".join(rendered_sections)

    substitutions = {
        "- `project_name`:": f"- `project_name`: {name}",
        "- `domain`:": f"- `domain`: {domain}",
        "- `owner`:": f"- `owner`: {owner}",
        "- `created_at`:": f"- `created_at`: {utc_now()[:10]}",
        "- `stack`:": f"- `stack`: {stack}",
    }
    # Assert each substitution actually fires exactly once. Template drift
    # (missing field OR duplicated field causing ambiguous replacement) would
    # otherwise produce a silently wrong profile.
    missing: list[str] = []
    duplicated: list[tuple[str, int]] = []
    for needle, replacement in substitutions.items():
        count = schema_body.count(needle)
        if count == 0:
            missing.append(needle)
            continue
        if count > 1:
            duplicated.append((needle, count))
            continue
        schema_body = schema_body.replace(needle, replacement, 1)
    if missing:
        raise SystemExit(
            "PROJECT_PROFILE.template.md structure drift: these needles were "
            "not found and no substitution was applied: "
            + ", ".join(repr(needle) for needle in missing)
            + ". Update either the template or scripts/bootstrap/new-project.py."
        )
    if duplicated:
        detail = ", ".join(f"{needle!r} x{n}" for needle, n in duplicated)
        raise SystemExit(
            "PROJECT_PROFILE.template.md structure drift: ambiguous needles "
            f"(each should appear exactly once): {detail}. "
            "Update either the template or scripts/bootstrap/new-project.py."
        )

    header = (
        f"# 프로젝트 프로필: {name}\n\n"
        f"<!-- scripts/bootstrap/new-project.py가 {utc_now()}에 생성했습니다. "
        f"자유롭게 수정하세요. 모르는 값은 `[NEEDS CLARIFICATION: <질문>]` "
        f"또는 `TBD`로 둡니다. -->\n\n"
    )
    output = target / "docs" / "PROJECT_PROFILE.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header + schema_body + "\n", encoding="utf-8")


def seed_knowledge(target: Path, name: str) -> None:
    """Create fresh knowledge files for the new project instead of inheriting
    the skeleton's own development history."""
    knowledge = target / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)

    # 컬럼명 "Superseded By"/"Superseded At"은 스키마 필드명이라 영어로 유지합니다.
    # scripts/wiki-lint.py 가 "superseded" 라는 표준 단어를 기준으로 supersession
    # 규칙을 검사하기 때문이며, 여기서 지우면 lint가 오탐합니다.
    index_body = (
        "# 지식 인덱스\n\n"
        "프로젝트의 장기 지식을 한 줄씩 정리하는 범위 제한 인덱스입니다. 상세 내용은\n"
        "`knowledge/log.md`, `knowledge/project-registry.md`, 또는 프로젝트별 파일에 둡니다.\n\n"
        "| ID | 주제 | 상태 | 출처 | Superseded By | Superseded At |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| K000 | 프로젝트 {name} 를 skeleton에서 초기화했습니다. | active | `runtime/activity-log.jsonl:1` | - | - |\n"
        "| K001 | 프로젝트 레지스트리에 재사용 가능한 결과와 회수 기록을 보존합니다. | active | `knowledge/project-registry.md:1` | - | - |\n\n"
        "## 인덱스 규칙\n\n"
        "- 지식 항목마다 한 줄씩만 씁니다.\n"
        "- 요약은 짧게 유지합니다.\n"
        "- 안정된 ID를 유지합니다.\n"
        "- 모든 항목은 출처(activity-log ts, file:line, URL 중 하나)를 포함해야 합니다.\n"
        "- 항목이 교체(superseded)되면 원래 행을 남기고 `superseded_by`와 `superseded_at`(`YYYY-MM-DD`)만 채웁니다.\n"
        "- 본문에 긴 참고자료를 붙여넣지 않습니다.\n"
        "- 상세 출처는 링크로만 연결합니다.\n"
    )
    (knowledge / "index.md").write_text(index_body, encoding="utf-8")

    log_body = (
        "# 지식 로그\n\n"
        "지식 변경을 시간순으로 기록하는 append-only 로그입니다.\n\n"
        f"## {utc_now()[:10]}\n\n"
        f"- 프로젝트 {name} 를 공용 AI 아키텍처 skeleton에서 초기화했습니다.\n\n"
        "## 로그 규칙\n\n"
        "- 새 항목은 위 또는 아래에 일관되게 추가합니다.\n"
        "- 기존 항목은 삭제하지 않고 정정 메모를 덧붙입니다.\n"
        "- 가능하면 근거 링크나 runtime 로그 참조를 함께 남깁니다.\n"
    )
    (knowledge / "log.md").write_text(log_body, encoding="utf-8")

    registry_body = (
        "# 프로젝트 레지스트리\n\n"
        "이 프로젝트의 재사용 가능한 결과와 회수 기록을 추적합니다.\n"
        "각 항목은 프로젝트 이름, 결과, 교훈, 참조 위치를 포함합니다.\n"
    )
    (knowledge / "project-registry.md").write_text(registry_body, encoding="utf-8")

    # lint-report.md는 scripts/wiki-lint.py가 재생성합니다.
    lint_placeholder = (
        "# 지식 위키 린트 리포트\n\n"
        "`python scripts/wiki-lint.py --write-report`를 실행하면 이 파일이 채워집니다.\n"
    )
    (knowledge / "lint-report.md").write_text(lint_placeholder, encoding="utf-8")


def seed_claude_settings(target: Path) -> None:
    """Write an empty Claude Code permissions file so the new project does not
    inherit the skeleton author's session-specific allow list."""
    dst = target / ".claude" / "settings.local.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        '{\n  "permissions": {\n    "allow": []\n  }\n}\n',
        encoding="utf-8",
    )


def seed_claude_entrypoint(target: Path) -> None:
    """Create Claude's entrypoint from AGENTS.md after generated artifacts are
    stripped from the copied tree."""
    dst = target / "CLAUDE.md"
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        dst.symlink_to("AGENTS.md")
    except OSError:
        shutil.copy2(target / "AGENTS.md", dst)


def seed_canonical_state(target: Path, name: str, domain: str, stack: str) -> None:
    """Initialize the canonical state/plan layer for a fresh project."""
    state = target / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "progress.md").write_text(
        "# Progress\n\n"
        "## 현재 마일스톤\n"
        "프로젝트 부트스트랩 완료 후 첫 plan 준비\n\n"
        "## 완료된 작업\n"
        "- 골격 부트스트랩\n\n"
        "## 다음 작업\n"
        "- 프로젝트 목표와 성공 기준 확정\n"
        "- 외부 레퍼런스 후보 검토 여부 결정\n",
        encoding="utf-8",
    )
    (state / "decisions.md").write_text(
        "# Decisions (append-only)\n\n"
        "> 형식: `## YYYY-MM-DD HH:MM — <결정 요약>` 다음 줄에 근거.\n"
        "> 절대 이전 결정을 수정/삭제하지 말 것. 번복은 새 항목으로 추가.\n\n"
        f"## {utc_now()} — 골격 부트스트랩\n"
        "- 사용 골격: AI_architecture canonical layer\n"
        "- 모드: codex-primary (v1)\n"
        f"- 프로젝트: {name}\n"
        f"- 도메인: {domain}\n"
        f"- 스택: {stack}\n",
        encoding="utf-8",
    )
    (state / "blockers.md").write_text("# Blockers\n\n(현재 없음)\n", encoding="utf-8")
    (state / "failures.jsonl").touch()
    (state / "cost-log.jsonl").touch()

    plans = target / "plans"
    for rel in ("active", "done", "failed"):
        directory = plans / rel
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").touch()
    (plans / "INDEX.md").write_text(
        "# Plans Index\n\n"
        "| seq | slug | status | created | replan | depends_on | parent | children |\n"
        "|-----|------|--------|---------|--------|------------|--------|----------|\n"
        "| (비어있음 — project-scaffolder 실행 후 첫 plan 등록) |\n\n"
        "## 라이프사이클\n"
        "- active/  : 진행 중\n"
        "- done/    : 완료\n"
        "- failed/  : 3회 재계획 실패 (회생 가능성 검토 대상)\n",
        encoding="utf-8",
    )


def seed_session_handoff(target: Path, _source: Path) -> None:
    """Always write a fresh blank handoff so the new project never inherits the
    skeleton author's (or any prior) session state, even if the skeleton's own
    handoff file has been overwritten with real data."""
    dst = target / "runtime" / "state" / "session-handoff.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    blank = (
        "# 세션 인수인계\n\n"
        "지금 어디까지 왔는지 보여주는 단일 현재 상태 파일입니다. 세션 종료, 컨텍스트\n"
        "한계 경고, 30분 단위 작업 종료 시 덮어쓰기(append 아님)로 갱신합니다.\n"
        "프로토콜: `docs/SESSION_CONTINUITY.md`.\n\n"
        "## Last updated\n\n"
        f"{utc_now()}\n\n"
        "## Current task\n\n"
        "<!-- 신규 프로젝트라 아직 진행 중인 작업이 없습니다. -->\n\n"
        "## Last completed\n\n"
        "- 프로젝트 skeleton 부트스트랩 완료\n\n"
        "## Next step\n\n1.\n\n"
        "## Open questions / blockers\n\n-\n\n"
        "## Files touched this session\n\n-\n\n"
        "## Key decisions\n\n-\n\n"
        "## Links\n\n-\n\n"
        "## Resume prompt\n\n"
        "이 파일을 먼저 읽고, 이어서 `runtime/activity-log.jsonl`의 최근 30줄,\n"
        "그 다음 `docs/PROJECT_PROFILE.md`를 확인한다. 신규 부트스트랩 직후라면\n"
        "활동 로그에 bootstrap 이벤트 한두 줄만 있을 수 있으니, 그 경우 바로\n"
        "사용자에게 이 프로젝트의 목표와 첫 작업을 질문한다. 목표가 정리되면\n"
        "`docs/REFERENCE_REVIEW.template.md`로 외부 레퍼런스를 검토하고,\n"
        "`docs/RUNTIME_STARTUP.template.md`로 실제 구동 계약을 만든다. 이전 세션 기록이\n"
        "있으면 1-2문장으로 요약한 뒤 \"Next step\" 1번을 다음 행동으로 제안한다.\n"
        "파일을 수정하기 전에는 사용자 의도와 현재 상태가 맞는지 먼저 확인한다.\n"
    )
    dst.write_text(blank, encoding="utf-8")


def append_initial_log(target: Path, name: str, domain: str, stack: str) -> None:
    runtime = target / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": utc_now(),
        "phase": "bootstrap",
        "action": "new_project_created",
        "project": name,
        "goal_lineage": [
            "bootstrap",
            name,
            "initialize project from common AI architecture skeleton",
        ],
        "tool_call": {
            "tool": "scripts/bootstrap/new-project.py",
            "status": "completed",
            "summary": "created project skeleton",
        },
        "data": {
            "domain": domain,
            "stack": stack,
        },
    }
    with (runtime / "activity-log.jsonl").open(
        "a", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
    (runtime / "agent-runs.jsonl").touch(exist_ok=True)
    (runtime / "install-state.jsonl").touch(exist_ok=True)
    (runtime / "skill-usage.jsonl").touch(exist_ok=True)
    (runtime / "skill-lifecycle.jsonl").touch(exist_ok=True)
    (runtime / "review-queue.jsonl").touch(exist_ok=True)
    (runtime / "reference-tasks.jsonl").touch(exist_ok=True)
    (runtime / "checkpoints.jsonl").touch(exist_ok=True)


def run_project_script(target: Path, rel_script: str, args: list[str]) -> None:
    script = target / rel_script
    if not script.exists():
        raise SystemExit(f"new-project failed: missing seeded script {rel_script}")
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(target), *args],
        cwd=str(target),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"new-project failed while running {rel_script}: {detail}")


def record_bootstrap_install_state(target: Path, profile: str) -> None:
    _, profiles = load_install_profiles(target)
    components = profiles.get(profile) or profiles.get("full-canonical") or []
    run_project_script(
        target,
        "scripts/install-state.py",
        [
            "add",
            "--event",
            "bootstrap_created",
            "--requested-profile",
            profile,
            "--validation-status",
            "unverified",
            *[arg for component in components for arg in ("--selected-component", component)],
        ],
    )


def build_generated_artifacts(target: Path) -> None:
    run_project_script(target, "scripts/convert.py", [])


def write_initial_session_snapshot(target: Path) -> None:
    run_project_script(target, "scripts/session-snapshot.py", ["write"])


NAME_MAX_LEN = 200
# Name flows into knowledge/index.md table cells AND into the activity-log
# event's `project` field. It must also be safe for filesystem-related uses
# down the line (e.g., embedded in file paths). Reject pipes, newlines, tabs,
# NUL, and path separators.
NAME_FORBIDDEN_CHARS = "|\n\r\t\x00/\\"
FIELD_FORBIDDEN_CHARS = "\n\r\x00"


def _validate_name(name: str) -> None:
    """Reject project names that would corrupt downstream Markdown tables,
    JSONL log lines, or file paths. `name` is embedded as a literal cell in
    the seeded knowledge index and as a project field in the activity log.
    """
    if not name or not name.strip():
        raise SystemExit("--name must not be empty")
    if len(name) > NAME_MAX_LEN:
        raise SystemExit(
            f"--name is {len(name)} chars; max is {NAME_MAX_LEN}"
        )
    bad = [ch for ch in NAME_FORBIDDEN_CHARS if ch in name]
    if bad:
        readable = ", ".join(repr(ch) for ch in bad)
        raise SystemExit(
            f"--name contains forbidden character(s) {readable}; "
            "pipes, newlines, tabs, NUL, and path separators (/ or \\) "
            "would corrupt the knowledge index table, JSONL log entries, "
            "or downstream file paths"
        )


def _validate_field(label: str, value: str) -> None:
    """Reject field values with line breaks that would break single-line
    Markdown bullets in the seeded PROJECT_PROFILE."""
    bad = [ch for ch in FIELD_FORBIDDEN_CHARS if ch in value]
    if bad:
        readable = ", ".join(repr(ch) for ch in bad)
        raise SystemExit(
            f"{label} contains forbidden character(s) {readable}; "
            "use a single-line value"
        )


def main() -> int:
    source = repo_root()
    default_profile, install_profiles = load_install_profiles(source)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--domain", default="general")
    parser.add_argument("--stack", default="unspecified")
    parser.add_argument("--owner", default="project owner")
    parser.add_argument("--profile", choices=sorted(install_profiles), default=default_profile)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow copying into a non-empty target.",
    )
    args = parser.parse_args()

    _validate_name(args.name)
    for label, value in (
        ("--domain", args.domain),
        ("--stack", args.stack),
        ("--owner", args.owner),
    ):
        _validate_field(label, value)

    # Reject the Windows "\\?\" long-path prefix up front. Path.resolve() on
    # such inputs returns a malformed drive-relative string like "C:Users\..."
    # which Python then anchors against the current working directory. In this
    # repo's layout that silently pointed the bootstrap at a path *inside the
    # skeleton itself* and recursively copied the skeleton into the skeleton
    # until MAX_PATH detonated the whole run. Cleaner to refuse the prefix and
    # ask the caller to pass the plain path; shutil on modern Windows handles
    # long paths fine without it. Match both the literal "\\?\" a user would
    # type at a prompt and the "\?\" collapsed form that Python's subprocess
    # (via the MSVC CRT quoting rules) delivers to argv.
    raw_target = args.target
    long_path_prefixes = ("\\\\?\\", "\\?\\", "//?/", "/?/")
    if raw_target.startswith(long_path_prefixes):
        raise SystemExit(
            "--target must not use the Windows '\\\\?\\' long-path prefix; "
            "pass the plain path instead (shutil handles long paths natively "
            "on Windows 10+ with LongPathsEnabled)."
        )
    target = Path(raw_target).resolve()
    if target == source:
        raise SystemExit("target must not be the skeleton root")
    # A target inside the skeleton would make copy_skeleton descend into its
    # own output: should_skip short-circuits the nested recursion, but the
    # outer copytree still creates a polluting subtree inside the skeleton
    # (e.g. skeleton/inner/nested/project/...). Refuse up front.
    if is_relative_to(target, source):
        raise SystemExit(
            f"--target ({target}) is inside the skeleton ({source}); "
            "choose a directory outside the skeleton tree"
        )
    if target.exists() and any(target.iterdir()) and not args.force:
        raise SystemExit(
            "target exists and is not empty; pass --force to merge into it"
        )
    # --force must not silently clobber user-authored project facts. The seed
    # functions unconditionally rewrite PROJECT_PROFILE.md, the knowledge/*
    # files, session-handoff.md, and .claude/settings.local.json. If any of
    # those already exist at the target with non-skeleton content, refuse
    # rather than eat the user's data. The caller can remove the specific
    # files they want regenerated.
    if args.force and target.exists():
        seeded_paths = [
            target / "docs" / "PROJECT_PROFILE.md",
            target / "knowledge" / "index.md",
            target / "knowledge" / "log.md",
            target / "knowledge" / "project-registry.md",
            target / "knowledge" / "lint-report.md",
            target / "runtime" / "state" / "session-handoff.md",
            target / "runtime" / "session-snapshot.json",
            target / ".claude" / "settings.local.json",
            target / "state" / "progress.md",
            target / "state" / "decisions.md",
            target / "plans" / "INDEX.md",
        ]
        collisions = [p for p in seeded_paths if p.is_file()]
        if collisions:
            rel = [str(p.relative_to(target)) for p in collisions]
            raise SystemExit(
                "--force would overwrite existing seeded file(s) at the "
                "target which may contain your project's real data: "
                + ", ".join(rel)
                + ". Move or delete the specific files you want "
                "regenerated, then re-run."
            )

    # Wrap filesystem work with a friendly error so operators get "couldn't
    # create X, check the parent path / permissions / drive" instead of a
    # four-frame pathlib traceback when --target points at a missing drive
    # or an unwritable location.
    try:
        copy_skeleton(source, target)
        empty_accumulated_dirs(target)
        seed_project_profile(target, source, args.name, args.domain, args.stack, args.owner)
        seed_knowledge(target, args.name)
        seed_canonical_state(target, args.name, args.domain, args.stack)
        seed_session_handoff(target, source)
        seed_claude_entrypoint(target)
        seed_claude_settings(target)
        append_initial_log(target, args.name, args.domain, args.stack)
        record_bootstrap_install_state(target, args.profile)
        build_generated_artifacts(target)
        write_initial_session_snapshot(target)
    except FileNotFoundError as exc:
        bad = exc.filename or target
        raise SystemExit(
            f"new-project failed: could not create or access {bad!r}. "
            f"Check that the parent directory of --target ({target.parent}) "
            f"is on a valid drive and is writable."
        )
    except PermissionError as exc:
        bad = exc.filename or target
        raise SystemExit(
            f"new-project failed: permission denied at {bad!r}. "
            f"Check write access to --target ({target}) and its parent."
        )
    except OSError as exc:
        raise SystemExit(
            f"new-project failed: filesystem error ({exc.__class__.__name__}) "
            f"on {exc.filename!r}: {exc.strerror or exc}. "
            f"Check --target ({target}) and its parent."
        )
    print(f"created {args.name} at {target}")
    print(f"profile: {args.profile}")
    print("")
    print("next steps:")
    print(f"  1. cd {target}")
    print("  2. python scripts/verify-skeleton.py  # health check the new project")
    print("  3. open Claude Code or Codex. Say one of: \"시작하자\" / \"프로젝트")
    print("     설정해줘\" / \"뭐부터 할까\". 목표를 미리 말할 필요 없음.")
    print("     에이전트가 CLAUDE.md/AGENTS.md를 읽고 먼저 질문을 시작한다.")
    print("     사용자는 답변만 하면 docs/PROJECT_PROFILE.md가 채워진다.")
    print("  4. 목표가 잡히면 관련 오픈소스/공식 문서/경쟁 제품 후보를 확인하고")
    print("     docs/REFERENCE_REVIEW.template.md 기준으로 채택 방식을 정한다.")
    print("  5. 구현 전에 docs/RUNTIME_STARTUP.template.md 기준으로 실행 명령,")
    print("     env, 포트, healthcheck, 첫 검증 명령을 고정한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
