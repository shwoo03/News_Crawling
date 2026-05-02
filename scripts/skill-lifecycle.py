#!/usr/bin/env python3
"""Track skill usage/evaluation and propose lifecycle changes."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


SUCCESS_OUTCOMES = {"success", "genuine_success", "pass", "passed"}
EXCLUDED_OUTCOMES = {"infra_error", "blocked_by_policy"}
USAGE_REQUIRED = ("ts", "skill", "event", "outcome", "run_id", "goal_lineage", "evidence_ref")
LIFECYCLE_REQUIRED = ("ts", "skill", "event", "status", "detail")
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)


@dataclass
class SkillUseRecord:
    ts: str
    skill: str
    event: str
    outcome: str
    run_id: str
    goal_lineage: list[str] = field(default_factory=list)
    evidence_ref: str = ""


@dataclass
class SkillLifecycleRecord:
    ts: str
    skill: str
    event: str
    status: str
    detail: str
    score: float | None = None
    goldens: int | None = None


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage_path(root: Path) -> Path:
    return root / "runtime" / "skill-usage.jsonl"


def lifecycle_path(root: Path) -> Path:
    return root / "runtime" / "skill-lifecycle.jsonl"


def read_jsonl(path: Path, root: Path) -> tuple[list[dict[str, Any]], list[str]]:
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
            findings.append(f"{path.relative_to(root).as_posix()}:{line_no} JSONL record must be an object")
            continue
        records.append(value)
    return records, findings


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def validate_usage(record: dict[str, Any], index: int) -> list[str]:
    label = f"usage record {index}"
    findings: list[str] = []
    for field_name in USAGE_REQUIRED:
        if field_name not in record:
            findings.append(f"{label} missing field `{field_name}`")
    for field_name in ("ts", "skill", "event", "outcome", "run_id"):
        if field_name in record and not str(record.get(field_name) or "").strip():
            findings.append(f"{label} field `{field_name}` is blank")
    if "goal_lineage" in record and not isinstance(record.get("goal_lineage"), list):
        findings.append(f"{label} field `goal_lineage` must be a list")
    return findings


def validate_lifecycle(record: dict[str, Any], index: int) -> list[str]:
    label = f"lifecycle record {index}"
    findings: list[str] = []
    for field_name in LIFECYCLE_REQUIRED:
        if field_name not in record:
            findings.append(f"{label} missing field `{field_name}`")
    for field_name in ("ts", "skill", "event", "status"):
        if field_name in record and not str(record.get(field_name) or "").strip():
            findings.append(f"{label} field `{field_name}` is blank")
    score = record.get("score")
    if score is not None and (not isinstance(score, (int, float)) or isinstance(score, bool) or score < 0 or score > 1):
        findings.append(f"{label} field `score` must be null or a number between 0 and 1")
    return findings


def parse_skill_name(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path.parent.name
    match = FRONTMATTER_RE.match(text)
    if not match:
        return path.parent.name
    for raw in match.group(1).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key.strip() == "name":
            return value.strip().strip("'\"") or path.parent.name
    return path.parent.name


def skill_statuses_with_findings(root: Path) -> tuple[dict[str, str], list[str]]:
    statuses: dict[str, str] = {}
    locations: dict[str, list[str]] = {}
    for base, status in (("skills/active", "active"), ("skills/_candidates", "candidate"), ("skills/_meta", "meta")):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            skill_file = path / "SKILL.md"
            if not path.is_dir() or not skill_file.exists():
                continue
            name = parse_skill_name(skill_file)
            statuses[name] = status
            locations.setdefault(name, []).append(path.relative_to(root).as_posix())
    findings = [
        f"duplicate skill name `{name}` in {', '.join(paths)}"
        for name, paths in sorted(locations.items())
        if len(paths) > 1
    ]
    return statuses, findings


def skill_locations(root: Path) -> dict[str, Path]:
    locations: dict[str, Path] = {}
    for base in ("skills/active", "skills/_candidates", "skills/_meta"):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            skill_file = path / "SKILL.md"
            if path.is_dir() and skill_file.exists():
                locations[parse_skill_name(skill_file)] = path
    return locations


def skill_statuses(root: Path) -> dict[str, str]:
    statuses, _ = skill_statuses_with_findings(root)
    return statuses


def parse_policy(root: Path) -> dict[str, float | int]:
    values: dict[str, float | int] = {
        "promote_min_uses": 20,
        "promote_min_success_rate": 0.85,
        "demote_threshold": 0.70,
    }
    path = root / "config" / "policy.yaml"
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.split("#", 1)[0].strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key not in values:
            continue
        try:
            values[key] = int(value) if key.endswith("_uses") else float(value)
        except ValueError:
            continue
    return values


def parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def success_rate(records: list[dict[str, Any]]) -> float | None:
    counted = [record for record in records if str(record.get("outcome") or "").lower() not in EXCLUDED_OUTCOMES]
    if not counted:
        return None
    successes = sum(1 for record in counted if str(record.get("outcome") or "").lower() in SUCCESS_OUTCOMES)
    return successes / len(counted)


def golden_count(path: Path | None) -> int:
    if not path:
        return 0
    return sum(1 for item in (path / "goldens").glob("*.yaml")) if (path / "goldens").is_dir() else 0


def pending_proposal_count(root: Path, skill: str) -> int:
    directory = root / "runtime" / "proposals" / "skill-lifecycle"
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.glob(f"*-{skill}-*.md") if path.is_file())


def build_health(root: Path) -> tuple[dict[str, Any], list[str]]:
    report, findings = build_report(root)
    usage, usage_findings = read_jsonl(usage_path(root), root)
    findings.extend(usage_findings)
    now = datetime.now(timezone.utc)
    locations = skill_locations(root)
    by_skill_usage: dict[str, list[dict[str, Any]]] = {}
    for record in usage:
        if record.get("event") == "use":
            by_skill_usage.setdefault(str(record.get("skill") or ""), []).append(record)
    health_items: list[dict[str, Any]] = []
    for item in report["skills"]:
        skill = item["skill"]
        records = by_skill_usage.get(skill, [])
        records7d: list[dict[str, Any]] = []
        records30d: list[dict[str, Any]] = []
        for record in records:
            ts = parse_ts(record.get("ts"))
            if not ts:
                continue
            age_days = (now - ts).total_seconds() / 86400
            if age_days <= 7:
                records7d.append(record)
            if age_days <= 30:
                records30d.append(record)
        rate7 = success_rate(records7d)
        rate30 = success_rate(records30d)
        if rate7 is None or rate30 is None:
            trend = "insufficient_data"
        elif rate7 + 0.1 < rate30:
            trend = "worsening"
        elif rate7 > rate30 + 0.1:
            trend = "improving"
        else:
            trend = "stable"
        failure_reasons: dict[str, int] = {}
        for record in records30d:
            outcome = str(record.get("outcome") or "").lower()
            if outcome in SUCCESS_OUTCOMES or outcome in EXCLUDED_OUTCOMES:
                continue
            reason = str(record.get("failure_reason") or outcome or "failure")
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        goldens = golden_count(locations.get(skill))
        recommendations: list[str] = []
        if goldens == 0:
            recommendations.append("add_golden_case")
        if trend == "worsening":
            recommendations.append("inspect_recent_failures")
        if item["recommendation"] != "none":
            recommendations.append(item["recommendation"])
        health_items.append({
            **item,
            "run_count_7d": len(records7d),
            "run_count_30d": len(records30d),
            "success_rate_7d": rate7,
            "success_rate_30d": rate30,
            "trend": trend,
            "goldens": goldens,
            "pending_proposals": pending_proposal_count(root, skill),
            "failure_reasons_30d": sorted(
                [{"reason": reason, "count": count} for reason, count in failure_reasons.items()],
                key=lambda value: (-value["count"], value["reason"]),
            )[:5],
            "health_recommendations": recommendations,
        })
    payload = {
        "generated_at": utc_now(),
        "usage_records": report["usage_records"],
        "skills": sorted(health_items, key=lambda value: (value["status"], value["skill"])),
        "findings": findings,
    }
    return payload, findings


def build_report(root: Path) -> tuple[dict[str, Any], list[str]]:
    usage, usage_findings = read_jsonl(usage_path(root), root)
    lifecycle, lifecycle_findings = read_jsonl(lifecycle_path(root), root)
    findings = usage_findings + lifecycle_findings
    for index, record in enumerate(usage, start=1):
        findings.extend(validate_usage(record, index))
    for index, record in enumerate(lifecycle, start=1):
        findings.extend(validate_lifecycle(record, index))

    statuses, duplicate_findings = skill_statuses_with_findings(root)
    findings.extend(duplicate_findings)
    policy = parse_policy(root)
    by_skill: dict[str, dict[str, Any]] = {
        name: {
            "skill": name,
            "status": status,
            "uses": 0,
            "successes": 0,
            "failures": 0,
            "excluded": 0,
            "success_rate": None,
            "latest_eval_score": None,
            "recommendation": "none",
        }
        for name, status in statuses.items()
    }
    for record in usage:
        skill = str(record.get("skill") or "")
        if not skill:
            continue
        item = by_skill.setdefault(skill, {
            "skill": skill,
            "status": "unknown",
            "uses": 0,
            "successes": 0,
            "failures": 0,
            "excluded": 0,
            "success_rate": None,
            "latest_eval_score": None,
            "recommendation": "none",
        })
        if record.get("event") != "use":
            continue
        outcome = str(record.get("outcome") or "").lower()
        if outcome in EXCLUDED_OUTCOMES:
            item["excluded"] += 1
            continue
        item["uses"] += 1
        if outcome in SUCCESS_OUTCOMES:
            item["successes"] += 1
        else:
            item["failures"] += 1
    for record in lifecycle:
        if record.get("event") != "evaluated":
            continue
        skill = str(record.get("skill") or "")
        if skill in by_skill and isinstance(record.get("score"), (int, float)):
            by_skill[skill]["latest_eval_score"] = float(record["score"])
    for item in by_skill.values():
        if item["uses"]:
            item["success_rate"] = item["successes"] / item["uses"]
        if (
            item["status"] == "candidate"
            and item["uses"] >= policy["promote_min_uses"]
            and item["success_rate"] is not None
            and item["success_rate"] >= policy["promote_min_success_rate"]
        ):
            item["recommendation"] = "promote"
        elif (
            item["status"] == "active"
            and item["uses"] > 0
            and item["success_rate"] is not None
            and item["success_rate"] < policy["demote_threshold"]
        ):
            item["recommendation"] = "demote"
    payload = {
        "policy": policy,
        "usage_records": len(usage),
        "lifecycle_records": len(lifecycle),
        "skills": sorted(by_skill.values(), key=lambda item: (item["status"], item["skill"])),
        "findings": findings,
    }
    return payload, findings


def cmd_record_use(root: Path, args: argparse.Namespace) -> int:
    record = SkillUseRecord(
        ts=args.ts or utc_now(),
        skill=args.skill,
        event="use",
        outcome=args.outcome,
        run_id=args.run_id,
        goal_lineage=args.goal_lineage or [],
        evidence_ref=args.evidence_ref,
    )
    findings = validate_usage(asdict(record), 1)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    append_jsonl(usage_path(root), asdict(record))
    print(json.dumps(asdict(record), ensure_ascii=False, indent=2) if args.format == "json" else f"recorded skill use: {record.skill}")
    return 0


def cmd_record_eval(root: Path, args: argparse.Namespace) -> int:
    record = SkillLifecycleRecord(
        ts=args.ts or utc_now(),
        skill=args.skill,
        event="evaluated",
        status=args.status,
        detail=args.detail,
        score=args.score,
        goldens=args.goldens,
    )
    findings = validate_lifecycle(asdict(record), 1)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    append_jsonl(lifecycle_path(root), asdict(record))
    print(json.dumps(asdict(record), ensure_ascii=False, indent=2) if args.format == "json" else f"recorded skill eval: {record.skill}")
    return 0


def cmd_report(root: Path, args: argparse.Namespace) -> int:
    payload, findings = build_report(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Skill Lifecycle")
        print(f"usage_records: {payload['usage_records']}")
        print(f"lifecycle_records: {payload['lifecycle_records']}")
        for item in payload["skills"]:
            rate = "n/a" if item["success_rate"] is None else f"{item['success_rate']:.3f}"
            print(f"  {item['status']:<9} {item['skill']}: uses={item['uses']} success_rate={rate} recommendation={item['recommendation']}")
        for finding in findings:
            print(f"  ERROR {finding}")
    return 1 if findings else 0


def cmd_health(root: Path, args: argparse.Namespace) -> int:
    payload, findings = build_health(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Skill Health")
        print(f"generated_at: {payload['generated_at']}")
        print(f"usage_records: {payload['usage_records']}")
        for item in payload["skills"]:
            rate7 = "n/a" if item["success_rate_7d"] is None else f"{item['success_rate_7d']:.3f}"
            rate30 = "n/a" if item["success_rate_30d"] is None else f"{item['success_rate_30d']:.3f}"
            recs = ", ".join(item["health_recommendations"]) or "none"
            print(
                f"  {item['status']:<9} {item['skill']}: "
                f"7d={rate7} 30d={rate30} trend={item['trend']} "
                f"goldens={item['goldens']} recommendations={recs}"
            )
        for finding in findings:
            print(f"  ERROR {finding}")
    return 1 if findings else 0


def cmd_propose(root: Path, args: argparse.Namespace) -> int:
    payload, findings = build_report(root)
    if findings:
        for finding in findings:
            print(f"ERROR {finding}", file=sys.stderr)
        return 1
    proposal_dir = root / "runtime" / "proposals" / "skill-lifecycle"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    today = utc_now()[:10]
    for item in payload["skills"]:
        recommendation = item["recommendation"]
        if recommendation not in {"promote", "demote"}:
            continue
        path = proposal_dir / f"{today}-{item['skill']}-{recommendation}.md"
        if path.exists():
            continue
        rate = "n/a" if item["success_rate"] is None else f"{item['success_rate']:.3f}"
        body = (
            f"# Skill Lifecycle Proposal: {item['skill']}\n\n"
            f"- `status`: proposed\n"
            f"- `proposal_type`: skill_{recommendation}\n"
            f"- `approval_required`: yes\n"
            f"- `created_at`: {utc_now()}\n\n"
            "## 근거\n\n"
            f"- current_status: {item['status']}\n"
            f"- uses: {item['uses']}\n"
            f"- successes: {item['successes']}\n"
            f"- success_rate: {rate}\n"
            f"- latest_eval_score: {item['latest_eval_score']}\n\n"
            "## 제안\n\n"
            f"- 사용자 승인 후 `{recommendation}` 처리합니다.\n"
            "- 이 파일은 제안서일 뿐 자동 적용이 아닙니다.\n"
        )
        path.write_text(body, encoding="utf-8")
        rel_path = path.relative_to(root).as_posix()
        written.append(rel_path)
        enqueue_skill_lifecycle_review(root, item["skill"], recommendation, rel_path)
    if args.format == "json":
        print(json.dumps({"written": written}, ensure_ascii=False, indent=2))
    else:
        print("no skill lifecycle proposals written" if not written else "\n".join(f"proposal: {item}" for item in written))
    return 0


def enqueue_skill_lifecycle_review(root: Path, skill: str, recommendation: str, proposal_rel: str) -> None:
    queue = root / "runtime" / "review-queue.jsonl"
    if queue.exists():
        text = queue.read_text(encoding="utf-8", errors="replace")
        if proposal_rel in text:
            return
    queue.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    event = {
        "ts": utc_now(),
        "action": "add",
        "id": f"review-{stamp}-{uuid.uuid4().hex[:8]}",
        "type": "skill-lifecycle",
        "title": f"Review skill {recommendation}: {skill}",
        "description": f"Skill lifecycle proposal requires user confirmation before {recommendation}.",
        "source_path": proposal_rel,
        "affected_paths": [proposal_rel],
        "search_queries": [],
        "options": ["accepted", "rejected", "deferred"],
    }
    with queue.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root (default: this skeleton root).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)

    use = sub.add_parser("record-use", help="Append one skill use event.")
    use.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    use.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    use.add_argument("--skill", required=True)
    use.add_argument("--outcome", default="success")
    use.add_argument("--run-id", required=True)
    use.add_argument("--goal-lineage", action="append", default=[])
    use.add_argument("--evidence-ref", default="")
    use.add_argument("--ts", default="")
    use.set_defaults(func=cmd_record_use)

    eval_parser = sub.add_parser("record-eval", help="Append one skill eval event.")
    eval_parser.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    eval_parser.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    eval_parser.add_argument("--skill", required=True)
    eval_parser.add_argument("--score", type=float, default=None)
    eval_parser.add_argument("--status", default="recorded")
    eval_parser.add_argument("--goldens", type=int, default=None)
    eval_parser.add_argument("--detail", default="")
    eval_parser.add_argument("--ts", default="")
    eval_parser.set_defaults(func=cmd_record_eval)

    report = sub.add_parser("report", help="Report skill lifecycle stats.")
    report.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    report.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    report.set_defaults(func=cmd_report)

    health = sub.add_parser("health", help="Report recent skill health, trends, and golden coverage.")
    health.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    health.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    health.set_defaults(func=cmd_health)

    propose = sub.add_parser("propose", help="Write review-only lifecycle proposals.")
    propose.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    propose.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    propose.set_defaults(func=cmd_propose)
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
