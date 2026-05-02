#!/usr/bin/env python3
"""Evaluate harness-level typed permission policy decisions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from lib_path_safety import evaluate_path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


VALID_ACTIONS = {"ask", "allow", "deny"}
VALID_DECISIONS = {"allow_once", "allow_session", "deny"}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def section(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*$", text, re.MULTILINE)
    if not match:
        return ""
    tail = text[match.end() :]
    next_key = re.search(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*$", tail, re.MULTILINE)
    return tail[: next_key.start()] if next_key else tail


def scalar(block: str, key: str, indent: int = 2) -> str:
    match = re.search(rf"^\s{{{indent}}}{re.escape(key)}:\s*([^\n#]+)", block, re.MULTILINE)
    return match.group(1).strip().strip('"').strip("'") if match else ""


def inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    return [item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()]


def load_policy(root: Path) -> dict[str, Any]:
    path = root / "config" / "policy.yaml"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    permissions = section(text, "permissions")
    confirmation_required = inline_list("[" + ",".join(re.findall(r"^\s{2}-\s*([A-Za-z0-9_-]+)\s*$", section(text, "confirmation_required"), re.MULTILINE)) + "]")
    rules: list[dict[str, Any]] = []
    for match in re.finditer(r"^\s{4}-\s+id:\s*([^\n#]+)(.*?)(?=^\s{4}-\s+id:|\Z)", permissions, re.MULTILINE | re.DOTALL):
        block = match.group(2)
        allowed = inline_list(scalar(block, "allowed_decisions", 6))
        rules.append(
            {
                "id": match.group(1).strip().strip('"').strip("'"),
                "match": scalar(block, "match", 6),
                "action": scalar(block, "action", 6),
                "allowed_decisions": allowed,
                "reason": scalar(block, "reason", 6),
            }
        )
    return {
        "default_action": scalar(permissions, "default_action") or "ask",
        "timeout_action": scalar(permissions, "timeout_action") or "deny",
        "decision_values": inline_list(scalar(permissions, "decision_values")),
        "confirmation_required": confirmation_required,
        "rules": rules,
    }


def match_pattern(pattern: str, action: str, resource: str) -> bool:
    target = f"{action}:{resource}" if resource else action
    if pattern.endswith("*"):
        return target.startswith(pattern[:-1]) or action.startswith(pattern[:-1])
    return pattern == target or pattern == action


def evaluate(root: Path, action: str, resource: str) -> dict[str, Any]:
    policy = load_policy(root)
    path_action = action in {"file_write", "file_delete", "dir_delete"}
    if path_action:
        operation = "delete" if action in {"file_delete", "dir_delete"} else "write"
        path_result = evaluate_path(root, resource, operation).to_dict()
        if path_result["decision"] == "deny":
            return {
                "action": action,
                "resource": resource,
                "decision": "deny",
                "allowed_decisions": [],
                "matched_rule": "path_safety",
                "reason": path_result["reason"],
                "timeout_action": policy["timeout_action"],
                "path_safety": path_result,
            }
    else:
        path_result = None
    if action in set(policy.get("confirmation_required") or []):
        return {
            "action": action,
            "resource": resource,
            "decision": "ask",
            "allowed_decisions": ["allow_once", "deny"],
            "matched_rule": "confirmation_required",
            "reason": "action is listed in confirmation_required",
            "timeout_action": policy["timeout_action"],
            "path_safety": path_result,
        }
    for rule in policy["rules"]:
        pattern = str(rule.get("match") or "")
        if pattern and match_pattern(pattern, action, resource):
            decision = str(rule.get("action") or "ask")
            if decision not in VALID_ACTIONS:
                decision = "deny"
            allowed = rule.get("allowed_decisions") if isinstance(rule.get("allowed_decisions"), list) else []
            if not allowed and decision == "ask":
                allowed = list(policy.get("decision_values") or sorted(VALID_DECISIONS))
            return {
                "action": action,
                "resource": resource,
                "decision": decision,
                "allowed_decisions": allowed,
                "matched_rule": rule.get("id"),
                "reason": rule.get("reason") or "",
                "timeout_action": policy["timeout_action"],
                "path_safety": path_result,
            }
    default = str(policy.get("default_action") or "ask")
    if default not in VALID_ACTIONS:
        default = "deny"
    return {
        "action": action,
        "resource": resource,
        "decision": default,
        "allowed_decisions": list(policy.get("decision_values") or sorted(VALID_DECISIONS)) if default == "ask" else [],
        "matched_rule": None,
        "reason": path_result["reason"] if path_result else "default permission action",
        "timeout_action": policy["timeout_action"],
        "path_safety": path_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--action", required=True)
    evaluate_parser.add_argument("--resource", default="")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    payload = evaluate(root, args.action, args.resource)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{payload['decision']} ({payload['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
