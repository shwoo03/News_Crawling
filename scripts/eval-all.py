#!/usr/bin/env python3
"""Run local golden-case checks across all canonical skill roots."""

from __future__ import annotations

import argparse
import importlib.util
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
class SkillEvalSummary:
    skill: str
    root: str
    status: str
    score: float | None
    pass_count: int
    fail_count: int
    skip_count: int
    detail: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_eval_module() -> Any:
    path = Path(__file__).resolve().parent / "eval.py"
    spec = importlib.util.spec_from_file_location("ai_architecture_eval", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def discover_skills(root: Path) -> list[tuple[str, str, Path]]:
    result: list[tuple[str, str, Path]] = []
    for base in ("skills/active", "skills/_candidates", "skills/_meta"):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_dir() and (path / "SKILL.md").exists():
                result.append((path.name, base, path))
    return result


def run_eval_all(root: Path) -> list[SkillEvalSummary]:
    eval_lib = load_eval_module()
    summaries: list[SkillEvalSummary] = []
    for skill_name, base, skill in discover_skills(root):
        golden_dir = skill / "goldens"
        results = [eval_lib.evaluate_case(path) for path in sorted(golden_dir.glob("*.yaml"))] if golden_dir.is_dir() else []
        if not results:
            summaries.append(SkillEvalSummary(skill_name, base, "WARN", None, 0, 0, 0, "regression_uncovered"))
            continue
        passed = sum(1 for item in results if item.status == "PASS")
        failed = sum(1 for item in results if item.status == "FAIL")
        skipped = sum(1 for item in results if item.status == "SKIP")
        scored = [item.score for item in results if item.score is not None]
        score = sum(scored) / len(scored) if scored else None
        status = "FAIL" if failed else "OK" if passed else "WARN"
        detail = f"{passed} pass, {failed} fail, {skipped} skip"
        summaries.append(SkillEvalSummary(skill_name, base, status, score, passed, failed, skipped, detail))
    return summaries


def render_text(results: list[SkillEvalSummary]) -> str:
    fail = sum(1 for item in results if item.status == "FAIL")
    warn = sum(1 for item in results if item.status == "WARN")
    ok = sum(1 for item in results if item.status == "OK")
    lines = ["Eval All", f"summary: {fail} fail, {warn} warn, {ok} ok"]
    for item in results:
        score = "n/a" if item.score is None else f"{item.score:.3f}"
        lines.append(f"  {item.status:<4} {item.skill} score={score}: {item.detail}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("command", nargs="?", choices=("run",), help=argparse.SUPPRESS)
    parser.add_argument("--root-after", dest="root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    results = run_eval_all(root)
    if args.format == "json":
        print(json.dumps({"root": str(root), "results": [asdict(item) for item in results]}, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))
    return 1 if any(item.status == "FAIL" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
