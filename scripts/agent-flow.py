#!/usr/bin/env python3
"""Single entrypoint for the common agent operating flows.

This script deliberately stays thin. It wraps the existing project tools in a
small number of commands so agents do not need to remember the internal order
of reference intake, proposal review, verification, and closeout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib_catalog import load_catalog_modes_with_status as load_shared_catalog_modes_with_status


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


DECISION_ALIASES = {"accept": "accepted", "reject": "rejected", "defer": "deferred"}
DECISIONS = {"accepted", "rejected", "deferred", *DECISION_ALIASES}
MODES = {"decide", "research", "build", "maintain", "closeout"}
REPO_MARKERS = {
    "README",
    "README.md",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
}
REPO_DIR_MARKERS = {".git", "scripts", "src", "tests"}
REFERENCE_ALIASES: dict[str, tuple[str, ...]] = {
    "ecc": ("everything-claude-code",),
    "everything claude code": ("everything-claude-code",),
    "everything-claude-code": ("everything-claude-code",),
    "opencode": ("opencode",),
    "open code": ("opencode",),
    "hermes": ("hermes-agent",),
    "hermes-agent": ("hermes-agent",),
    "llm wiki": ("llm_wiki",),
    "llm-wiki": ("llm_wiki",),
    "llm_wiki": ("llm_wiki",),
    "paperclip": ("paperclip",),
}
DEFAULT_MODE_CONFIGS: dict[str, dict[str, Any]] = {
    "research": [
        ("goal_pattern", r"(오픈소스|open\s*source|oss|reference|레퍼런스|참고|비슷한|기존\s*서비스|클론|clone|분석|찾아|찾고|새\s*프로젝트|프로젝트\s*시작)"),
        ("reason", "자연어 요청에 새 프로젝트, 오픈소스, 레퍼런스, 클론, 분석 의도가 포함되어 reference-first 흐름이 적합합니다."),
        ("next_command", "python3 scripts/agent-flow.py research --auto --format json"),
        ("confidence", "high"),
        ("requires_confirmation", False),
        ("write_policy", "read_only"),
        ("signal", "goal_mentions_reference"),
        ("suggested_questions", [
            "프로젝트 타입은 webapp, cli, lib, api, data-pipeline 중 무엇에 가깝나요?",
            "우선 참고해야 할 레퍼런스나 경쟁 서비스가 있나요?",
            "MVP가 성공했다고 볼 수 있는 최소 기준은 무엇인가요?",
        ]),
    ],
    "closeout": [
        ("goal_pattern", r"(검증|마무리|완료|종료|closeout|quality\s*gate|verify)"),
        ("reason", "자연어 요청이 검증, 완료, 마무리 흐름을 요구합니다."),
        ("next_command", 'python3 scripts/agent-flow.py closeout --goal "{goal}" --changed-path . --format json'),
        ("confidence", "high"),
        ("requires_confirmation", True),
        ("write_policy", "write_with_confirmation"),
        ("signal", "goal_mentions_closeout"),
        ("suggested_questions", [
            "완료 증거에 기록할 목표명은 무엇인가요?",
            "이번 작업에서 바뀐 주요 경로는 어디인가요?",
            "검증에서 반드시 확인해야 할 기대 결과는 무엇인가요?",
        ]),
    ],
    "maintain": [
        ("goal_pattern", r"(스켈레톤|뼈대|하네스|운영\s*시스템|시스템\s*개선|agent-flow|agent\s*flow|시스템\s*구조|구조\s*개선|AI_architecture|catalog|카탈로그)"),
        ("reason", "자연어 요청이 스켈레톤이나 운영 시스템 자체 개선에 가깝습니다."),
        ("next_command", "manual: clarify maintain target, implement approved changes, then run agent-flow closeout"),
        ("confidence", "medium"),
        ("requires_confirmation", False),
        ("write_policy", "manual_work_required"),
        ("signal", "goal_mentions_maintain"),
        ("suggested_questions", [
            "개선하려는 대상은 라우팅, 검증, 문서, 스킬, 레퍼런스 흐름 중 어디인가요?",
            "단순화, 자동화, 안정성 중 무엇을 가장 우선할까요?",
            "반드시 유지해야 하는 기존 동작이나 호환성이 있나요?",
        ]),
    ],
    "build": [
        ("reason", "자연어 요청에 reference, maintain, closeout 신호가 없어 일반 구현 흐름으로 분류합니다."),
        ("next_command", "manual: clarify build scope, implement approved changes, then run agent-flow closeout"),
        ("confidence", "medium"),
        ("requires_confirmation", False),
        ("write_policy", "manual_work_required"),
        ("signal", "goal_mentions_build"),
        ("suggested_questions", [
            "이번에 구현할 정확한 범위는 어디까지인가요?",
            "완료 여부를 판단할 수용 기준이나 테스트 시나리오는 무엇인가요?",
            "선호하는 스택, 라이브러리, 피해야 할 제약이 있나요?",
        ]),
    ],
    "decide": [
        ("reason", "열린 review queue 항목이 있어 새 작업보다 사용자 결정 동기화가 우선입니다."),
        ("next_command", "python3 scripts/agent-flow.py decide --proposal <proposal-path> --decision accepted|rejected|deferred --by <name> --format json"),
        ("confidence", "high"),
        ("requires_confirmation", True),
        ("write_policy", "read_only"),
        ("signal", "open_review_queue"),
        ("suggested_questions", [
            "이 proposal은 accepted, rejected, deferred 중 무엇으로 기록할까요?",
            "그 결정을 내리는 핵심 근거는 무엇인가요?",
            "승인한다면 실제 반영 범위는 어디까지인가요?",
        ]),
    ],
}
for _mode, _items in list(DEFAULT_MODE_CONFIGS.items()):
    DEFAULT_MODE_CONFIGS[_mode] = dict(_items)

FAILURE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("timeout", ("timed out", "timeout", "deadline exceeded")),
    ("auth", ("unauthorized", "authentication", "forbidden", "invalid api key", "permission denied")),
    ("quota", ("rate limit", "quota", "too many requests", "429", "insufficient credits")),
    ("format", ("jsondecode", "invalid json", "parse error", "schema", "frontmatter", "yaml")),
    ("payload", ("payload too large", "request entity too large", "maximum context", "context length", "too many tokens")),
    ("policy", ("blocked by policy", "confirmation required", "outside repo", "not allowed", "denied by policy")),
    ("infra", ("connection refused", "dns", "network", "no such file", "not found", "exit 127", "broken pipe")),
]


@dataclass
class CommandResult:
    name: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def resolve_under_root(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    resolved.relative_to(root.resolve(strict=False))
    return resolved


def rel_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def run_command(root: Path, name: str, command: list[str], timeout: int) -> CommandResult:
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=command_env(),
            timeout=timeout,
        )
        return CommandResult(name, command, result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(name, command, 124, stdout, stderr or f"timed out after {timeout}s")


def compact_output(value: str, *, max_chars: int = 800) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def classify_failure(text: str) -> str:
    haystack = text.lower()
    for category, needles in FAILURE_RULES:
        if any(needle in haystack for needle in needles):
            return category
    return "unknown"


def result_payload(result: CommandResult) -> dict[str, Any]:
    payload = {
        "name": result.name,
        "exit_code": result.exit_code,
        "ok": result.ok,
        "stdout": compact_output(result.stdout),
        "stderr": compact_output(result.stderr),
    }
    if not result.ok:
        payload["failure_type"] = classify_failure((result.stdout or "") + "\n" + (result.stderr or ""))
    return payload


def prevalidated_check_payload(result: CommandResult) -> str:
    return json.dumps(
        {
            "name": result.name,
            "status": "OK" if result.ok else "FAIL",
            "command": result.command,
            "exit_code": result.exit_code,
            "detail": compact_output((result.stdout or "") + "\n" + (result.stderr or "")),
            "failure_type": "" if result.ok else classify_failure((result.stdout or "") + "\n" + (result.stderr or "")),
        },
        ensure_ascii=False,
    )


def read_json_stdout(result: CommandResult, fallback: Any) -> Any:
    if not result.ok:
        return fallback
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return fallback


def count_markdown_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    ignored = {"README.md", "_template.md"}
    return sum(1 for item in path.glob("*.md") if item.name not in ignored and item.is_file())


def review_queue_count(root: Path, timeout: int) -> tuple[int, CommandResult | None]:
    script = root / "scripts" / "review-queue.py"
    if not script.exists():
        return 0, None
    result = run_command(root, "review-queue-count", [sys.executable, str(script), "--root", str(root), "count", "--json"], timeout)
    payload = read_json_stdout(result, {})
    return int(payload.get("open", 0)) if isinstance(payload, dict) else 0, result


def handoff_summary(root: Path) -> dict[str, Any]:
    path = root / "runtime" / "state" / "session-handoff.md"
    if not path.exists():
        return {"exists": False, "path": rel_to_root(root, path), "summary": ""}
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    return {"exists": True, "path": rel_to_root(root, path), "summary": " | ".join(lines[:3])}


def recommended_next_action(open_reviews: int, candidate_count: int, proposal_count: int) -> str:
    if open_reviews:
        return "decide"
    if candidate_count == 0 and proposal_count == 0:
        return "research"
    return "closeout"


def recommended_action_from_routing(routing: dict[str, Any]) -> str:
    mode = str(routing.get("mode") or "").strip()
    next_action_type = str(routing.get("next_action_type") or "").strip()
    if next_action_type == "manual_work_required":
        return mode or "manual_work_required"
    return mode or "build"


def shell_command(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def load_catalog_modes_with_status(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return load_shared_catalog_modes_with_status(root, DEFAULT_MODE_CONFIGS, MODES)


def load_catalog_modes(root: Path) -> dict[str, dict[str, Any]]:
    modes, _status = load_catalog_modes_with_status(root)
    return modes


def command_requires_confirmation(command: str, configured: bool) -> bool:
    if configured:
        return True
    write_markers = ("--write-card", "--proposal", "--record", "--apply")
    return any(marker in command for marker in write_markers)


def route_requires_confirmation(command: str, configured: bool, write_policy: str) -> bool:
    return write_policy == "write_with_confirmation" or command_requires_confirmation(command, configured)


def next_action_type_for(mode: str, command: str, *, requires_confirmation: bool = False) -> str:
    if command.startswith("manual:"):
        return "manual_work_required"
    if mode == "decide":
        return "user_decision_required"
    if requires_confirmation:
        return "confirmation_required"
    return "agent_flow_command"


def write_policy_for(config: dict[str, Any], mode: str) -> str:
    value = str(config.get("write_policy") or DEFAULT_MODE_CONFIGS.get(mode, {}).get("write_policy") or "").strip()
    if value in {"read_only", "manual_work_required", "write_with_confirmation"}:
        return value
    if mode in {"build", "maintain"}:
        return "manual_work_required"
    if mode == "closeout":
        return "write_with_confirmation"
    return "read_only"


def format_catalog_command(template: str, *, goal: str = "", proposal: str = "") -> str:
    if "{goal}" in template:
        command = template.replace('"{goal}"', shell_command([goal])).replace("{goal}", shlex.quote(goal))
    else:
        command = template
    if proposal:
        command = command.replace("<proposal-path>", proposal)
    if goal and "agent-flow.py research" in command and "--goal" not in command:
        command = f"{command} --goal {shell_command([goal])}"
    return command


def build_intake_for(root: Path, goal: str, catalog_modes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    build_questions = suggested_questions_for_mode(root, "build")
    return {
        "goal": goal,
        "plan_required": True,
        "plan_location": "plans/active/<seq>-<slug>.md",
        "scope_questions": build_questions[:1] or ["이번에 구현할 정확한 범위는 어디까지인가요?"],
        "acceptance_criteria_questions": build_questions[1:2] or ["완료 여부를 판단할 수용 기준이나 테스트 시나리오는 무엇인가요?"],
        "constraint_questions": build_questions[2:] or ["선호하는 스택, 라이브러리, 피해야 할 제약이 있나요?"],
        "reference_required": has_reference_signal(goal, catalog_modes),
        "closeout_command_template": 'python3 scripts/agent-flow.py closeout --goal "<goal>" --changed-path <path> --format json',
    }


def oss_discovery_for(goal: str, local_candidates: int) -> dict[str, Any]:
    lowered = goal.lower()
    wants_network = bool(re.search(r"(인터넷|검색|search|github|깃허브|clone|클론|찾아|찾고|오픈소스)", lowered, re.IGNORECASE))
    suggested = wants_network and local_candidates == 0
    return {
        "suggested": suggested,
        "requires_confirmation": suggested,
        "reason": "local reference candidates are missing and the goal asks for OSS search/clone" if suggested else "",
        "approval_flow": "candidate 10 -> recency/audit/license dry-run -> finalist 3 -> user decision" if suggested else "",
    }


def first_open_review_source(root: Path, timeout: int) -> str:
    items, _ = load_review_items(root, timeout)
    for item in items:
        if item.get("status") == "open":
            return str(item.get("source_path") or "")
    return ""


def reference_task_summary(root: Path, timeout: int) -> dict[str, Any]:
    script = root / "scripts" / "reference-task-queue.py"
    if not script.exists():
        return {"available": False, "counts": {}, "open": 0}
    result = run_command(root, "reference-task-queue-list", [sys.executable, str(script), "--root", str(root), "list", "--format", "json"], timeout)
    payload = read_json_stdout(result, [])
    counts: dict[str, int] = {}
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                status = str(item.get("status", ""))
                counts[status] = counts.get(status, 0) + 1
    return {
        "available": True,
        "counts": counts,
        "open": counts.get("queued", 0) + counts.get("running", 0),
        "check": result_payload(result),
    }


def has_reference_signal(goal: str, catalog_modes: dict[str, dict[str, Any]]) -> bool:
    if not goal:
        return False
    research_pattern = str(catalog_modes.get("research", {}).get("goal_pattern") or "")
    extra_pattern = r"(ECC|everything-claude-code|opencode|benchmark|비교|성숙한\s*레퍼런스|레퍼런스들\s*참고)"
    return bool(
        (research_pattern and re.search(research_pattern, goal, re.IGNORECASE))
        or re.search(extra_pattern, goal, re.IGNORECASE)
    )


def project_state_signals(open_reviews: int, candidate_count: int, proposal_count: int) -> list[str]:
    signals: list[str] = []
    signals.append("open_review_queue" if open_reviews else "no_open_review_queue")
    signals.append("reference_candidates_exist" if candidate_count else "no_reference_candidates")
    signals.append("reference_proposals_exist" if proposal_count else "no_reference_proposals")
    return signals


def suggested_questions_for_mode(root: Path, mode: str) -> list[str]:
    questions = load_catalog_modes(root).get(mode, {}).get("suggested_questions", [])
    return list(questions) if isinstance(questions, list) else []


def classify_start(
    root: Path,
    args: argparse.Namespace,
    open_reviews: int,
    candidate_count: int,
    proposal_count: int,
    active_reference_tasks: int = 0,
) -> dict[str, Any]:
    goal = (args.goal or "").strip()
    base_signals = project_state_signals(open_reviews, candidate_count, proposal_count)
    catalog_modes, catalog_status = load_catalog_modes_with_status(root)
    if open_reviews:
        source_path = first_open_review_source(root, args.timeout)
        config = catalog_modes["decide"]
        next_command = format_catalog_command(str(config.get("next_command") or DEFAULT_MODE_CONFIGS["decide"]["next_command"]), proposal=source_path or "<proposal-path>")
        write_policy = write_policy_for(config, "decide")
        requires_confirmation = route_requires_confirmation(next_command, bool(config.get("requires_confirmation", True)), write_policy)
        return {
            "mode": "decide",
            "reason": str(config.get("reason") or DEFAULT_MODE_CONFIGS["decide"]["reason"]),
            "next_command": next_command,
            "next_action_type": next_action_type_for("decide", next_command, requires_confirmation=requires_confirmation),
            "confidence": "high" if source_path else "medium",
            "requires_confirmation": requires_confirmation,
            "write_policy": write_policy,
            "signals": base_signals,
            "catalog_status": catalog_status,
        }
    maintain_config = catalog_modes["maintain"]
    maintain_pattern = str(maintain_config.get("goal_pattern") or "")
    if goal and maintain_pattern and re.search(maintain_pattern, goal, re.IGNORECASE) and has_reference_signal(goal, catalog_modes):
        next_command = format_catalog_command("python3 scripts/agent-flow.py research --auto --format json", goal=goal)
        return {
            "mode": "maintain",
            "reason": "운영 시스템 개선 요청이면서 성숙한 레퍼런스 비교 신호가 있어 구현보다 reference review를 먼저 수행합니다.",
            "next_command": next_command,
            "next_action_type": "reference_review_required",
            "confidence": "high",
            "requires_confirmation": False,
            "write_policy": "read_only",
            "signals": [*base_signals, "goal_mentions_maintain", "goal_mentions_reference", "reference_review_required"],
            "catalog_status": catalog_status,
        }
    for mode in ("research", "closeout", "maintain"):
        config = catalog_modes[mode]
        pattern = str(config.get("goal_pattern") or "")
        if goal and pattern and re.search(pattern, goal, re.IGNORECASE):
            next_command = format_catalog_command(str(config.get("next_command") or DEFAULT_MODE_CONFIGS[mode]["next_command"]), goal=goal)
            write_policy = write_policy_for(config, mode)
            requires_confirmation = route_requires_confirmation(next_command, bool(config.get("requires_confirmation", False)), write_policy)
            return {
                "mode": mode,
                "reason": str(config.get("reason") or DEFAULT_MODE_CONFIGS[mode]["reason"]),
                "next_command": next_command,
                "next_action_type": next_action_type_for(mode, next_command, requires_confirmation=requires_confirmation),
                "confidence": str(config.get("confidence") or DEFAULT_MODE_CONFIGS[mode]["confidence"]),
                "requires_confirmation": requires_confirmation,
                "write_policy": write_policy,
                "signals": [*base_signals, str(config.get("signal") or DEFAULT_MODE_CONFIGS[mode]["signal"])],
                "catalog_status": catalog_status,
            }
    if goal:
        config = catalog_modes["build"]
        next_command = format_catalog_command(str(config.get("next_command") or DEFAULT_MODE_CONFIGS["build"]["next_command"]), goal=goal)
        write_policy = write_policy_for(config, "build")
        requires_confirmation = route_requires_confirmation(next_command, bool(config.get("requires_confirmation", False)), write_policy)
        return {
            "mode": "build",
            "reason": str(config.get("reason") or DEFAULT_MODE_CONFIGS["build"]["reason"]),
            "next_command": next_command,
            "next_action_type": next_action_type_for("build", next_command, requires_confirmation=requires_confirmation),
            "confidence": str(config.get("confidence") or "medium"),
            "requires_confirmation": requires_confirmation,
            "write_policy": write_policy,
            "signals": [*base_signals, str(config.get("signal") or "goal_mentions_build")],
            "catalog_status": catalog_status,
        }
    legacy = recommended_next_action(open_reviews, candidate_count, proposal_count)
    if legacy == "research":
        config = catalog_modes["research"]
        next_command = format_catalog_command("python3 scripts/agent-flow.py research --auto --format json", goal=goal)
        return {
            "mode": "research",
            "reason": "아직 reference 후보 카드와 proposal이 없어 먼저 reference 후보를 분석하는 것이 안전합니다.",
            "next_command": next_command,
            "next_action_type": "agent_flow_command",
            "confidence": "medium",
            "requires_confirmation": False,
            "write_policy": write_policy_for(config, "research"),
            "signals": [*base_signals, "no_goal_provided"],
            "catalog_status": catalog_status,
        }
    if active_reference_tasks:
        return {
            "mode": "research",
            "reason": "진행 중인 reference task가 있어 새 작업보다 reference queue 상태 확인이 우선입니다.",
            "next_command": "python3 scripts/reference-task-queue.py --root . list --format json",
            "next_action_type": "manual_work_required",
            "confidence": "medium",
            "requires_confirmation": False,
            "write_policy": "read_only",
            "signals": [*base_signals, "no_goal_provided", "active_reference_task"],
            "catalog_status": catalog_status,
        }
    if legacy == "closeout":
        return {
            "mode": "build",
            "reason": "기존 reference 후보나 proposal은 있지만 명시적 목표가 없어 closeout을 자동 추천하지 않습니다. 먼저 다음 작업 범위를 확인해야 합니다.",
            "next_command": "manual: clarify current goal before research/build/closeout",
            "next_action_type": "manual_work_required",
            "confidence": "low",
            "requires_confirmation": False,
            "write_policy": "manual_work_required",
            "signals": [*base_signals, "no_goal_provided"],
            "catalog_status": catalog_status,
        }
    return {
        "mode": "build",
        "reason": "열린 결정이나 명확한 reference-first 신호가 없어 일반 구현 흐름으로 분류합니다.",
        "next_command": "manual: clarify build scope, implement approved changes, then run agent-flow closeout",
        "next_action_type": "manual_work_required",
        "confidence": "low" if not goal else "medium",
        "requires_confirmation": False,
        "write_policy": "manual_work_required",
        "signals": [*base_signals, "no_goal_provided"],
        "catalog_status": catalog_status,
    }


def render_start_text(payload: dict[str, Any]) -> str:
    lines = [
        "Agent Flow Start",
        f"root: {payload['root']}",
        f"review_queue_count: {payload['review_queue_count']}",
        f"reference_candidates: {payload['reference_candidates']}",
        f"reference_proposals: {payload['reference_proposals']}",
        f"handoff_exists: {payload['handoff']['exists']}",
        f"recommended_next_action: {payload['recommended_next_action']}",
        f"mode: {payload['mode']}",
        f"reason: {payload['reason']}",
        f"next_command: {payload['next_command']}",
        f"next_action_type: {payload['next_action_type']}",
        f"confidence: {payload['confidence']}",
        f"requires_confirmation: {payload['requires_confirmation']}",
        f"write_policy: {payload['write_policy']}",
        f"catalog_status: {payload['catalog_status']['source']} ({payload['catalog_status']['detail']})",
        f"signals: {', '.join(payload['signals'])}",
        f"reference_tasks_open: {payload['reference_tasks'].get('open', 0)}",
    ]
    if payload.get("suggested_questions"):
        lines.append("suggested_questions:")
        lines.extend(f"  - {question}" for question in payload["suggested_questions"])
    if payload["handoff"].get("summary"):
        lines.append(f"handoff_summary: {payload['handoff']['summary']}")
    return "\n".join(lines)


def cmd_start(root: Path, args: argparse.Namespace) -> int:
    open_reviews, queue_result = review_queue_count(root, args.timeout)
    candidate_count = count_markdown_files(root / "research" / "reference-candidates")
    proposal_count = count_markdown_files(root / "runtime" / "proposals" / "reference-adoption")
    ref_tasks = reference_task_summary(root, args.timeout)
    routing = classify_start(root, args, open_reviews, candidate_count, proposal_count, int(ref_tasks.get("open", 0) or 0))
    catalog_modes, _catalog_status = load_catalog_modes_with_status(root)
    discovery = oss_discovery_for(args.goal or "", candidate_count)
    signals = list(routing.get("signals", []))
    if discovery.get("suggested") and "oss_discovery_suggested" not in signals:
        signals.append("oss_discovery_suggested")
        routing["signals"] = signals
    payload = {
        "root": str(root),
        "goal": args.goal,
        "review_queue_count": open_reviews,
        "reference_candidates": candidate_count,
        "reference_proposals": proposal_count,
        "handoff": handoff_summary(root),
        "recommended_next_action": recommended_action_from_routing(routing),
        **routing,
        "build_intake": build_intake_for(root, args.goal or "", catalog_modes) if routing.get("mode") == "build" else {},
        "oss_discovery_suggested": discovery,
        "reference_tasks": ref_tasks,
        "suggested_questions": suggested_questions_for_mode(root, str(routing["mode"])),
        "checks": [result_payload(queue_result)] if queue_result else [],
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_start_text(payload))
    return 0


def is_repo_like(path: Path) -> bool:
    if not path.is_dir():
        return False
    score = 0
    for marker in REPO_MARKERS:
        if (path / marker).exists():
            score += 1
    for marker in REPO_DIR_MARKERS:
        if (path / marker).is_dir():
            score += 1
    return score >= 2


def existing_candidate_text(root: Path) -> str:
    cards = root / "research" / "reference-candidates"
    if not cards.is_dir():
        return ""
    chunks: list[str] = []
    for path in cards.glob("*.md"):
        if path.name in {"README.md", "_template.md"}:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks).lower()


def normalize_reference_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def reference_name_terms(value: str) -> set[str]:
    normalized = normalize_reference_name(value)
    terms = {normalized, normalized.replace("-", ""), normalized.replace("-", " ")}
    return {term for term in terms if term}


def configured_reference_targets(goal: str, prefer: list[str], exclude: list[str]) -> tuple[set[str], set[str], list[str]]:
    matched_terms: list[str] = []
    targets: set[str] = set()
    for value in prefer:
        normalized = normalize_reference_name(value)
        if normalized:
            targets.add(normalized)
            matched_terms.append(value)
        for alias, canonical_values in REFERENCE_ALIASES.items():
            if normalized == normalize_reference_name(alias):
                targets.update(normalize_reference_name(item) for item in canonical_values)
    lowered = goal.lower()
    for alias, canonical_values in REFERENCE_ALIASES.items():
        if alias.lower() in lowered:
            matched_terms.append(alias)
            targets.update(normalize_reference_name(item) for item in canonical_values)
    excluded: set[str] = set()
    for value in exclude:
        normalized = normalize_reference_name(value)
        if normalized:
            excluded.add(normalized)
        for alias, canonical_values in REFERENCE_ALIASES.items():
            if normalized == normalize_reference_name(alias):
                excluded.update(normalize_reference_name(item) for item in canonical_values)
    return targets, excluded, matched_terms


def candidate_matches_names(path: Path, names: set[str]) -> bool:
    if not names:
        return False
    haystack = {
        normalize_reference_name(path.name),
        normalize_reference_name(path.resolve(strict=False).as_posix()),
    }
    haystack.update(reference_name_terms(path.name))
    return any(name in haystack or name in normalize_reference_name(path.resolve(strict=False).as_posix()) for name in names)


def reference_memory(root: Path, path: Path) -> dict[str, Any]:
    target_name = normalize_reference_name(path.name)
    target_abs = path.resolve(strict=False).as_posix().lower()
    memory: dict[str, Any] = {
        "candidate_card": "",
        "proposal": "",
        "decision": "",
        "last_reviewed_at": "",
        "recommended_action": "create_candidate_card",
    }
    cards = root / "research" / "reference-candidates"
    if cards.is_dir():
        for card in sorted(cards.glob("*.md")):
            if card.name in {"README.md", "_template.md"}:
                continue
            text = card.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            name_match = re.search(r"- `name`:\s*([^\n]+)", text)
            url_match = re.search(r"- `url`:\s*([^\n]+)", text)
            local_match = re.search(r"- `local_clone_path`:\s*([^\n]+)", text)
            card_name = normalize_reference_name(name_match.group(1)) if name_match else ""
            card_paths = " ".join(match.group(1).strip().lower() for match in (url_match, local_match) if match)
            if card_name == target_name or target_abs in lowered or target_name in normalize_reference_name(card_paths):
                memory["candidate_card"] = rel_to_root(root, card)
                reviewed = re.search(r"- `reviewed_at`:\s*([^\n]+)", text) or re.search(r"- `created_at`:\s*([^\n]+)", text)
                if reviewed:
                    memory["last_reviewed_at"] = reviewed.group(1).strip()
                break
    proposals = root / "runtime" / "proposals" / "reference-adoption"
    if proposals.is_dir():
        card_rel = str(memory.get("candidate_card") or "")
        for proposal in sorted(proposals.glob("*.md")):
            text = proposal.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            if (card_rel and card_rel in text) or target_abs in lowered:
                memory["proposal"] = rel_to_root(root, proposal)
                decision = re.search(r"- `decision`:\s*([^\n]*)", text) or re.search(r"- `status`:\s*([^\n]+)", text)
                if decision:
                    memory["decision"] = decision.group(1).strip()
                break
    if memory["candidate_card"]:
        memory["recommended_action"] = "reuse_existing_card"
    if memory["proposal"] and memory["decision"] in {"accepted", "rejected", "deferred", "pending"}:
        memory["recommended_action"] = "review_existing_proposal"
    return memory


def candidate_search_roots(root: Path) -> list[Path]:
    result = [root / "runtime" / "external-repos"]
    sibling = root.parent / "AI_architecture_references"
    if sibling.exists():
        result.append(sibling)
    return result


def repo_candidates_under(search_root: Path, *, max_depth: int = 3) -> list[Path]:
    if not search_root.is_dir():
        return []
    root_depth = len(search_root.resolve(strict=False).parts)
    candidates: list[Path] = []
    for current, dirs, _files in os.walk(search_root):
        path = Path(current)
        depth = len(path.resolve(strict=False).parts) - root_depth
        if depth > max_depth:
            dirs[:] = []
            continue
        if path != search_root and is_repo_like(path):
            candidates.append(path)
            dirs[:] = []
    return candidates


def auto_reference_score(root: Path, path: Path, *, goal_matches: set[str] | None = None, prefer_matches: set[str] | None = None) -> int:
    analyzed = existing_candidate_text(root)
    haystacks = {path.name.lower(), path.resolve(strict=False).as_posix().lower()}
    already_seen = any(value and value in analyzed for value in haystacks)
    marker_score = sum(1 for marker in REPO_MARKERS if (path / marker).exists())
    marker_score += sum(1 for marker in REPO_DIR_MARKERS if (path / marker).is_dir())
    named = candidate_matches_names(path, goal_matches or set())
    preferred = candidate_matches_names(path, prefer_matches or set())
    freshness = 0 if already_seen and not named and not preferred else 100
    sibling_bonus = 10 if path.is_relative_to(root.parent / "AI_architecture_references") else 0
    goal_bonus = 1000 if named else 0
    prefer_bonus = 2000 if preferred else 0
    return prefer_bonus + goal_bonus + freshness + sibling_bonus + marker_score


def reference_candidate_payload(
    root: Path,
    path: Path,
    *,
    explicit: bool = False,
    goal_matches: set[str] | None = None,
    prefer_matches: set[str] | None = None,
) -> dict[str, Any]:
    reason, signals = reference_selection_details(root, path, explicit=explicit, goal_matches=goal_matches, prefer_matches=prefer_matches)
    memory = reference_memory(root, path)
    return {
        "path": rel_to_root(root, path),
        "score": 0 if explicit else auto_reference_score(root, path, goal_matches=goal_matches, prefer_matches=prefer_matches),
        "selection_reason": reason,
        "selection_signals": signals,
        "reference_memory": memory,
        "reuse_existing_card_suggested": memory.get("recommended_action") in {"reuse_existing_card", "review_existing_proposal"},
    }


def rank_auto_references(root: Path, *, limit: int = 3, goal: str = "", prefer: list[str] | None = None, exclude: list[str] | None = None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    seen: set[str] = set()
    candidates: list[Path] = []
    prefer_targets, _prefer_excluded, prefer_terms = configured_reference_targets("", prefer or [], [])
    _ignored_targets, exclude_targets, _exclude_terms = configured_reference_targets("", [], exclude or [])
    goal_targets, _unused_excluded, goal_terms = configured_reference_targets(goal, [], [])
    matched_terms = [*prefer_terms]
    matched_terms.extend(term for term in goal_terms if term not in matched_terms)
    excluded_references: list[str] = []
    for search_root in candidate_search_roots(root):
        for candidate in repo_candidates_under(search_root):
            key = candidate.resolve(strict=False).as_posix()
            if key not in seen:
                seen.add(key)
                if candidate_matches_names(candidate, exclude_targets):
                    excluded_references.append(rel_to_root(root, candidate))
                    continue
                candidates.append(candidate)
    ranked = sorted(
        candidates,
        key=lambda path: (
            auto_reference_score(root, path, goal_matches=goal_targets, prefer_matches=prefer_targets),
            path.name.lower(),
        ),
        reverse=True,
    )
    return (
        [reference_candidate_payload(root, path, goal_matches=goal_targets, prefer_matches=prefer_targets) for path in ranked[:limit]],
        matched_terms,
        excluded_references,
    )


def select_auto_reference(root: Path) -> Path | None:
    ranked, _matched, _excluded = rank_auto_references(root, limit=1)
    if not ranked:
        return None
    value = str(ranked[0]["path"])
    path = Path(value)
    return path if path.is_absolute() else (root / path)


def present_repo_markers(path: Path) -> list[str]:
    markers: list[str] = []
    for marker in sorted(REPO_MARKERS):
        if (path / marker).exists():
            markers.append(marker)
    for marker in sorted(REPO_DIR_MARKERS):
        if (path / marker).is_dir():
            markers.append(marker)
    return markers


def reference_selection_details(
    root: Path,
    target: Path,
    *,
    explicit: bool,
    goal_matches: set[str] | None = None,
    prefer_matches: set[str] | None = None,
) -> tuple[str, list[str]]:
    if explicit:
        return "explicit local path", ["explicit_local_path"]
    signals: list[str] = []
    if candidate_matches_names(target, prefer_matches or set()):
        signals.append("prefer_match")
    if candidate_matches_names(target, goal_matches or set()):
        signals.append("goal_reference_match")
    try:
        target.relative_to((root / "runtime" / "external-repos").resolve(strict=False))
        signals.append("runtime_external_repo")
    except ValueError:
        pass
    try:
        target.relative_to((root.parent / "AI_architecture_references").resolve(strict=False))
        signals.append("sibling_reference_repo")
    except ValueError:
        pass
    markers = present_repo_markers(target)
    if markers:
        signals.append("repo_markers:" + ",".join(markers))
    memory = reference_memory(root, target)
    if memory.get("candidate_card"):
        signals.append("already_candidate_carded")
        signals.append("already_reviewed")
    else:
        signals.append("not_yet_candidate_carded")
    location = "sibling reference repo" if "sibling_reference_repo" in signals else "runtime external repo"
    return f"{location}; {signals[-1]}; markers={','.join(markers) or 'none'}", signals


def parse_created_path(root: Path, stdout: str) -> str:
    for line in stdout.splitlines():
        match = re.match(r"^created\s+(.+?)\s*$", line.strip())
        if match:
            value = match.group(1).strip()
            path = Path(value)
            return value if not path.is_absolute() else rel_to_root(root, path)
    return ""


def cmd_research(root: Path, args: argparse.Namespace) -> int:
    target: Path
    reference_candidates: list[dict[str, Any]] = []
    matched_goal_terms: list[str] = []
    excluded_references: list[str] = []
    use_local_path_arg = False
    explicit_selection = False
    if args.local_path:
        target = resolve_under_root(root, args.local_path)
        use_local_path_arg = True
        explicit_selection = True
        reference_candidates = [reference_candidate_payload(root, target, explicit=True)]
    elif args.auto:
        reference_candidates, matched_goal_terms, excluded_references = rank_auto_references(
            root,
            limit=3,
            goal=args.goal,
            prefer=args.prefer,
            exclude=args.exclude,
        )
        if not reference_candidates:
            print("no auto reference candidates found under runtime/external-repos/ or ../AI_architecture_references/", file=sys.stderr)
            return 1
        selected_value = str(reference_candidates[0]["path"])
        selected = Path(selected_value)
        if not selected.is_absolute():
            selected = root / selected
        target = selected.resolve(strict=False)
        try:
            target.relative_to(root.resolve(strict=False))
            use_local_path_arg = True
        except ValueError:
            use_local_path_arg = False
    else:
        print("research requires --local-path <path> or --auto", file=sys.stderr)
        return 2
    target_ref = rel_to_root(root, target)
    prefer_targets, _exclude_targets, _prefer_terms = configured_reference_targets("", args.prefer, [])
    goal_targets, _unused, _goal_terms = configured_reference_targets(args.goal, [], [])
    selection_reason, selection_signals = reference_selection_details(root, target, explicit=explicit_selection, goal_matches=goal_targets, prefer_matches=prefer_targets)
    memory = reference_memory(root, target)
    task_id = ""
    task_commands: list[CommandResult] = []
    if args.write_card and args.proposal and (root / "scripts" / "reference-task-queue.py").exists():
        task_result = run_command(
            root,
            "reference-task-add",
            [
                sys.executable,
                str(root / "scripts" / "reference-task-queue.py"),
                "--root",
                str(root),
                "add",
                "--target",
                target_ref,
                "--goal",
                args.searched_for,
                "--format",
                "json",
            ],
            args.timeout,
        )
        task_commands.append(task_result)
        task_payload = read_json_stdout(task_result, {})
        if isinstance(task_payload, dict):
            task_id = str(task_payload.get("id", ""))
    card_command = [
        sys.executable,
        str(root / "scripts" / "reference-intake.py"),
        "--root",
        str(root),
        "card-draft",
    ]
    if use_local_path_arg:
        card_command.extend(["--local-path", target_ref])
    else:
        card_command.append(str(target))
    card_command.extend([
        "--url",
        args.url or target_ref,
        "--searched-for",
        args.searched_for,
    ])
    if args.name:
        card_command.extend(["--name", args.name])
    if task_id:
        card_command.extend(["--reference-task-id", task_id])
    if args.write_card:
        card_command.append("--write")
    card_result = run_command(root, "reference-card-draft", card_command, args.timeout)
    commands = [*task_commands, card_result]
    candidate_path = parse_created_path(root, card_result.stdout) if args.write_card else ""
    proposal_path = ""

    if args.proposal and not args.write_card:
        commands.append(CommandResult("proposal-precondition", [], 2, "", "--proposal requires --write-card"))
    if card_result.ok and args.write_card:
        commands.append(
            run_command(
                root,
                "validate-reference-candidates",
                [sys.executable, str(root / "scripts" / "validate-reference-candidates.py"), "--root", str(root)],
                args.timeout,
            )
        )
    if card_result.ok and args.write_card and args.proposal and candidate_path:
        proposal_result = run_command(
            root,
            "create-reference-proposal",
            [
                sys.executable,
                str(root / "scripts" / "create-reference-proposal.py"),
                "--root",
                str(root),
                "--candidate",
                candidate_path,
                "--write",
            ],
            args.timeout,
        )
        commands.append(proposal_result)
        proposal_path = parse_created_path(root, proposal_result.stdout)
        if proposal_result.ok:
            commands.append(
                run_command(
                    root,
                    "validate-reference-proposals",
                    [sys.executable, str(root / "scripts" / "validate-reference-proposals.py"), "--root", str(root)],
                    args.timeout,
                )
            )
            if task_id and (root / "scripts" / "reference-task-queue.py").exists():
                commands.append(
                    run_command(
                        root,
                        "reference-task-complete",
                        [
                            sys.executable,
                            str(root / "scripts" / "reference-task-queue.py"),
                            "--root",
                            str(root),
                            "complete",
                            task_id,
                            "--candidate-card",
                            candidate_path,
                            "--proposal",
                            proposal_path,
                            "--format",
                            "json",
                        ],
                        args.timeout,
                    )
                )
    payload = {
        "root": str(root),
        "mode": "write" if args.write_card else "preview",
        "selected_reference": target_ref,
        "auto": bool(args.auto and not args.local_path),
        "selection_reason": selection_reason,
        "selection_signals": selection_signals,
        "reference_candidates": reference_candidates,
        "matched_goal_terms": matched_goal_terms,
        "excluded_references": excluded_references,
        "reference_memory": memory,
        "reuse_existing_card_suggested": memory.get("recommended_action") in {"reuse_existing_card", "review_existing_proposal"},
        "candidate_path": candidate_path,
        "proposal_path": proposal_path,
        "reference_task_id": task_id,
        "commands": [result_payload(result) for result in commands],
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.write_card:
        print(f"selected_reference: {target_ref}")
        print(f"candidate_path: {candidate_path or '(not created)'}")
        if args.proposal:
            print(f"proposal_path: {proposal_path or '(not created)'}")
        for result in commands:
            print(f"{'OK' if result.ok else 'FAIL'} {result.name}: exit {result.exit_code}")
            if result.stderr.strip():
                print(compact_output(result.stderr))
    else:
        print(card_result.stdout, end="" if card_result.stdout.endswith("\n") else "\n")
        if card_result.stderr:
            print(card_result.stderr, file=sys.stderr, end="" if card_result.stderr.endswith("\n") else "\n")
    return 0 if all(result.ok for result in commands) else 1


def set_backtick_field(text: str, field: str, value: str) -> str:
    pattern = re.compile(rf"^-[ \t]+`{re.escape(field)}`:[ \t]*.*$", re.MULTILINE)
    replacement = f"- `{field}`: {value}"
    if pattern.search(text):
        return pattern.sub(replacement, text)
    return text.rstrip() + "\n" + replacement + "\n"


def load_review_items(root: Path, timeout: int) -> tuple[list[dict[str, Any]], CommandResult | None]:
    script = root / "scripts" / "review-queue.py"
    if not script.exists():
        return [], None
    result = run_command(root, "review-queue-list", [sys.executable, str(script), "--root", str(root), "list", "--all", "--json"], timeout)
    payload = read_json_stdout(result, [])
    return payload if isinstance(payload, list) else [], result


def find_review_for_proposal(items: list[dict[str, Any]], proposal_rel: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("status") in {"resolved", "dismissed"}:
            continue
        paths = [str(item.get("source_path", "")), *[str(value) for value in item.get("affected_paths", [])]]
        if proposal_rel in paths:
            return item
    return None


def append_activity(root: Path, proposal_rel: str, args: argparse.Namespace) -> str:
    path = root / "runtime" / "activity-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": utc_now(),
        "phase": "reference",
        "action": "reference_decision",
        "project": root.name,
        "data": {
            "proposal": proposal_rel,
            "decision": args.decision,
            "decided_by": args.by,
            "note": args.note,
        },
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    return rel_to_root(root, path)


def cmd_decide(root: Path, args: argparse.Namespace) -> int:
    args.decision = DECISION_ALIASES.get(args.decision, args.decision)
    proposal = resolve_under_root(root, args.proposal)
    if not proposal.is_file():
        print(f"proposal not found: {proposal}", file=sys.stderr)
        return 2
    proposal_rel = rel_to_root(root, proposal)
    text = proposal.read_text(encoding="utf-8")
    status = {"accepted": "accepted", "rejected": "rejected", "deferred": "deferred"}[args.decision]
    updated = text
    for field, value in (
        ("status", status),
        ("decision", args.decision),
        ("decided_at", utc_now()),
        ("decided_by", args.by),
        ("decision_source", "agent-flow decide"),
    ):
        updated = set_backtick_field(updated, field, value)
    if args.decision == "accepted":
        updated = set_backtick_field(updated, "validation_result", "pending implementation")
    proposal.write_text(updated, encoding="utf-8")

    items, list_result = load_review_items(root, args.timeout)
    commands: list[CommandResult] = []
    if list_result:
        commands.append(list_result)
    review_item = find_review_for_proposal(items, proposal_rel)
    queue_action = "none"
    if review_item:
        item_id = str(review_item["id"])
        if args.decision == "deferred":
            queue_command = [
                sys.executable,
                str(root / "scripts" / "review-queue.py"),
                "--root",
                str(root),
                "defer",
                item_id,
                "--note",
                args.note or "deferred by agent-flow decide",
            ]
            queue_action = "deferred"
        else:
            queue_command = [
                sys.executable,
                str(root / "scripts" / "review-queue.py"),
                "--root",
                str(root),
                "resolve",
                item_id,
                "--decision",
                args.decision,
                "--note",
                args.note,
            ]
            queue_action = "resolved"
        commands.append(run_command(root, f"review-queue-{queue_action}", queue_command, args.timeout))
    activity_path = append_activity(root, proposal_rel, args)
    payload = {
        "root": str(root),
        "proposal_path": proposal_rel,
        "decision": args.decision,
        "decided_by": args.by,
        "review_item_id": review_item.get("id", "") if review_item else "",
        "review_queue_action": queue_action,
        "activity_log": activity_path,
        "commands": [result_payload(result) for result in commands],
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"decision: {args.decision}")
        print(f"proposal_path: {proposal_rel}")
        print(f"review_queue_action: {queue_action}")
        print(f"activity_log: {activity_path}")
    return 0 if all(result.ok for result in commands) else 1


def cmd_closeout(root: Path, args: argparse.Namespace) -> int:
    commands = [
        run_command(root, "verify", [sys.executable, str(root / "scripts" / "verify.py"), "--root", str(root)], args.timeout),
    ]
    if commands[-1].ok:
        commands.append(
            run_command(
                root,
                "quality-gate",
                [sys.executable, str(root / "scripts" / "quality-gate.py"), "--root", str(root), "--format", "json", "--strict"],
                args.timeout,
            )
        )
    checks_ok = all(result.ok for result in commands)
    recorded = False
    if checks_ok:
        closeout_command = [
            sys.executable,
            str(root / "scripts" / "task-closeout.py"),
            "--root",
            str(root),
            "--goal",
            args.goal,
            "--record",
            "--format",
            "json",
            "--profile",
            args.profile,
        ]
        for path in args.changed_path or ["."]:
            closeout_command.extend(["--changed-path", path])
        for skill in args.skill:
            closeout_command.extend(["--skill", skill])
        for result in commands:
            closeout_command.extend(["--prevalidated-check", prevalidated_check_payload(result)])
        closeout_result = run_command(root, "task-closeout", closeout_command, args.timeout)
        commands.append(closeout_result)
        recorded = closeout_result.ok
    payload = {
        "root": str(root),
        "goal": args.goal,
        "recorded": recorded,
        "skipped_record_reason": "" if checks_ok else "verify_or_quality_gate_failed",
        "commands": [result_payload(result) for result in commands],
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"goal: {args.goal}")
        for result in commands:
            print(f"{'OK' if result.ok else 'FAIL'} {result.name}: exit {result.exit_code}")
            if result.stderr.strip():
                print(compact_output(result.stderr))
        print(f"recorded: {recorded}")
    return 0 if all(result.ok for result in commands) and (not checks_ok or recorded) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Summarize current project state and next action.")
    start.add_argument("--goal", default="", help="Natural-language user goal to classify into the next flow.")
    start.add_argument("--format", choices=("text", "json"), default="text")
    start.add_argument("--timeout", type=int, default=60)
    start.set_defaults(func=cmd_start)

    research = sub.add_parser("research", help="Analyze a local reference and optionally create proposal artifacts.")
    research.add_argument("--local-path", default="", help="Local reference path inside the project root.")
    research.add_argument("--auto", action="store_true", help="Automatically select a local reference candidate.")
    research.add_argument("--goal", default="", help="Natural-language goal used to prioritize named references.")
    research.add_argument("--prefer", action="append", default=[], help="Reference name to prioritize. Repeatable.")
    research.add_argument("--exclude", action="append", default=[], help="Reference name to exclude. Repeatable.")
    research.add_argument("--url", default="")
    research.add_argument("--searched-for", default="local reference analysis")
    research.add_argument("--name", default="")
    research.add_argument("--write-card", action="store_true")
    research.add_argument("--proposal", action="store_true")
    research.add_argument("--format", choices=("text", "json"), default="text")
    research.add_argument("--timeout", type=int, default=60)
    research.set_defaults(func=cmd_research)

    decide = sub.add_parser("decide", help="Apply a human decision to a proposal and review queue item.")
    decide.add_argument("--proposal", required=True)
    decide.add_argument("--decision", required=True, choices=sorted(DECISIONS))
    decide.add_argument("--by", required=True)
    decide.add_argument("--note", default="")
    decide.add_argument("--format", choices=("text", "json"), default="text")
    decide.add_argument("--timeout", type=int, default=60)
    decide.set_defaults(func=cmd_decide)

    closeout = sub.add_parser("closeout", help="Run verification and record closeout evidence when safe.")
    closeout.add_argument("--goal", required=True)
    closeout.add_argument("--changed-path", action="append", default=[])
    closeout.add_argument("--skill", action="append", default=[])
    closeout.add_argument("--profile", default="auto")
    closeout.add_argument("--format", choices=("text", "json"), default="text")
    closeout.add_argument("--timeout", type=int, default=120)
    closeout.set_defaults(func=cmd_closeout)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    try:
        return args.func(root, args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
