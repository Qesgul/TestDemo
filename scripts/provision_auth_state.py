#!/usr/bin/env python3
"""Deprecated compatibility wrapper for account_session_provider prepare."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.account_session_provider import command_prepare


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--tag")
    parser.add_argument("--username")
    parser.add_argument("--mode", choices=("cookie",), default="cookie")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--allow-sensitive-output", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    args.require_tag = [args.tag] if args.tag else []
    return command_prepare(args)


if __name__ == "__main__":
    raise SystemExit(main())
