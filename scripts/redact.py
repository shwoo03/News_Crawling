#!/usr/bin/env python3
"""Redact secret-like values before runtime logging."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b")),
    ("generic_secret", re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]{12,}")),
]


def redact_text(value: str) -> str:
    text = value
    for label, pattern in PATTERNS:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return text


def redact_json(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_json(item) for key, item in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    output = redact_text(args.text or sys.stdin.read())
    if args.format == "json":
        print(json.dumps({"redacted": output}, ensure_ascii=False, indent=2))
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
