#!/usr/bin/env python3
"""Classify validation/tool failure text into stable operational categories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


CATEGORIES = ("auth", "quota", "timeout", "format", "payload", "policy", "infra", "unknown")
RULES: list[tuple[str, tuple[str, ...], bool, str]] = [
    ("timeout", ("timed out", "timeout", "deadline exceeded"), True, "Retry once after checking whether the command is expected to be long-running."),
    ("auth", ("unauthorized", "authentication", "forbidden", "invalid api key", "permission denied"), False, "Check credentials, tokens, and access scope before retrying."),
    ("quota", ("rate limit", "quota", "too many requests", "429", "insufficient credits"), True, "Wait, reduce request volume, or switch to a cheaper/local validation path."),
    ("format", ("jsondecode", "invalid json", "parse error", "schema", "frontmatter", "yaml"), False, "Fix the output/file format and rerun the validator."),
    ("payload", ("payload too large", "request entity too large", "maximum context", "context length", "too many tokens"), False, "Reduce input size or split the work into smaller batches."),
    ("policy", ("blocked by policy", "confirmation required", "outside repo", "not allowed", "denied by policy"), False, "Ask for approval or narrow the action to the allowed policy scope."),
    ("infra", ("connection refused", "dns", "network", "no such file", "not found", "exit 127", "broken pipe"), True, "Check local service/process availability and tool installation."),
]


def classify(text: str) -> dict[str, Any]:
    haystack = text.lower()
    for category, needles, retryable, next_action in RULES:
        for needle in needles:
            if needle in haystack:
                return {
                    "category": category,
                    "retryable": retryable,
                    "matched": needle,
                    "next_action": next_action,
                }
    return {
        "category": "unknown",
        "retryable": False,
        "matched": "",
        "next_action": "Inspect stderr/stdout and add a more specific classifier rule if this repeats.",
    }


def render_text(payload: dict[str, Any]) -> str:
    return (
        "Failure Classification\n"
        f"category: {payload['category']}\n"
        f"retryable: {payload['retryable']}\n"
        f"matched: {payload['matched'] or 'n/a'}\n"
        f"next_action: {payload['next_action']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="", help="Failure text to classify.")
    parser.add_argument("--file", default="", help="Read failure text from a file.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    text = args.text
    if args.file:
        try:
            text += "\n" + Path(args.file).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"could not read {args.file}: {exc}", file=sys.stderr)
            return 2
    payload = classify(text)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
