#!/usr/bin/env python3
"""Evaluate whether a proposed write/delete path is safe for the harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib_path_safety import evaluate_path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--path", required=True)
    check.add_argument("--operation", choices=("write", "delete"), default="write")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root().resolve()
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2
    result = evaluate_path(root, args.path, args.operation).to_dict()
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['decision']} ({result['reason']})")
    return 1 if result["decision"] == "deny" else 0


if __name__ == "__main__":
    raise SystemExit(main())
