#!/usr/bin/env python3
"""Run local golden-case regression checks for a skill.

This v1 evaluator supports deterministic `schema-check` and `heuristic`
goldens locally. `llm-as-judge` cases are discovered and reported as skipped
unless a future role runner is wired in through config/roles.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


@dataclass
class CaseResult:
    id: str
    path: str
    status: str
    score: float | None
    detail: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    current_block: list[str] | None = None
    parent_key: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if current_block is not None and indent > 0:
            current_block.append(raw[2:] if raw.startswith("  ") else line)
            continue
        current_block = None
        if indent == 0 and line.endswith(":") and line[:-1] in {"expected_properties", "forbidden_patterns"}:
            current_key = line[:-1]
            current_list = []
            data[current_key] = current_list
            parent_key = None
            continue
        if indent == 0 and line.endswith(":"):
            parent_key = line[:-1]
            data.setdefault(parent_key, {})
            current_key = None
            current_list = None
            continue
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            value = value.strip()
            if value == "|":
                current_block = []
                data[key] = current_block
            else:
                data[key] = value.strip("'\"")
            current_key = key
            current_list = None
            parent_key = None
            continue
        if indent == 0 and line.startswith("- ") and current_key:
            data.setdefault(current_key, []).append(line[2:].strip())
            continue
        if indent == 0:
            current_key = None
            current_list = None
            continue
        if indent == 2 and line.startswith("- ") and current_key:
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(line[2:].strip())
            continue
        if indent == 2 and parent_key and ":" in line:
            key, value = line.split(":", 1)
            parent = data.setdefault(parent_key, {})
            if isinstance(parent, dict):
                parent[key.strip()] = value.strip().strip("'\"")
    for key, value in list(data.items()):
        if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            data[key] = "\n".join(value) if key in {"input", "actual_output", "output", "notes"} else value
    return data


def find_skill(root: Path, name: str) -> Path | None:
    for base in ("skills/active", "skills/_candidates", "skills/_meta"):
        candidate = root / base / name
        if candidate.is_dir():
            return candidate
    return None


def evaluate_case(path: Path) -> CaseResult:
    case = parse_simple_yaml(path)
    case_id = str(case.get("id") or path.stem)
    evaluation = case.get("evaluation") if isinstance(case.get("evaluation"), dict) else {}
    method = str(evaluation.get("judge_method") or "schema-check")
    threshold = float(evaluation.get("pass_threshold") or 0.8)
    if method == "llm-as-judge":
        return CaseResult(case_id, path.as_posix(), "SKIP", None, "llm-as-judge is not wired in v1 local eval")

    output_value = case.get("actual_output") if case.get("actual_output") is not None else case.get("output")
    if output_value is None:
        return CaseResult(case_id, path.as_posix(), "SKIP", None, "no output to evaluate")
    output = str(output_value)
    expected = case.get("expected_properties") if isinstance(case.get("expected_properties"), list) else []
    forbidden = case.get("forbidden_patterns") if isinstance(case.get("forbidden_patterns"), list) else []
    checks = len(expected) + len(forbidden)
    if checks == 0:
        return CaseResult(case_id, path.as_posix(), "SKIP", None, "no expected_properties or forbidden_patterns")

    passed = 0
    missing: list[str] = []
    present_forbidden: list[str] = []
    for item in expected:
        needle = str(item)
        if needle in output:
            passed += 1
        else:
            missing.append(needle)
    for item in forbidden:
        needle = str(item)
        if needle in output:
            present_forbidden.append(needle)
        else:
            passed += 1
    score = passed / checks
    if score >= threshold and not present_forbidden:
        return CaseResult(case_id, path.as_posix(), "PASS", score, "local golden passed")
    detail = []
    if missing:
        detail.append(f"missing expected={missing}")
    if present_forbidden:
        detail.append(f"forbidden present={present_forbidden}")
    return CaseResult(case_id, path.as_posix(), "FAIL", score, "; ".join(detail) or "below threshold")


def run_eval(root: Path, skill_name: str) -> tuple[Path | None, list[CaseResult]]:
    skill = find_skill(root, skill_name)
    if skill is None:
        return None, []
    golden_dir = skill / "goldens"
    if not golden_dir.is_dir():
        return skill, []
    return skill, [evaluate_case(path) for path in sorted(golden_dir.glob("*.yaml"))]


def render_text(skill: Path | None, results: list[CaseResult], skill_name: str) -> str:
    if skill is None:
        return f"skill not found: {skill_name}"
    if not results:
        return f"skill: {skill_name}\nscore: n/a\nstatus: regression_uncovered\nno golden cases found"
    passed = sum(1 for item in results if item.status == "PASS")
    failed = sum(1 for item in results if item.status == "FAIL")
    skipped = sum(1 for item in results if item.status == "SKIP")
    scored = [item.score for item in results if item.score is not None]
    score = sum(scored) / len(scored) if scored else None
    lines = [
        f"skill: {skill_name}",
        f"score: {'n/a' if score is None else round(score, 3)}",
        f"summary: {passed} pass, {failed} fail, {skipped} skip",
    ]
    for item in results:
        score_text = "n/a" if item.score is None else f"{item.score:.3f}"
        lines.append(f"  {item.status:<4} {item.id} score={score_text}: {item.detail}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_name")
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    skill, results = run_eval(root, args.skill_name)
    if args.format == "json":
        print(json.dumps({"skill": args.skill_name, "skill_dir": str(skill) if skill else None, "results": [asdict(r) for r in results]}, ensure_ascii=False, indent=2))
    else:
        print(render_text(skill, results, args.skill_name))
    if skill is None:
        return 2
    return 1 if any(item.status == "FAIL" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
