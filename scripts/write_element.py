#!/usr/bin/env python
"""
Append a single element entry to a YAML elements file.

Usage:
    python scripts/write_element.py \\
        --yaml pages/elements/my_elements.yaml \\
        --key "step3_提交按钮" \\
        --spec '{"type":"css","selector":"#OperationForm-btnSubmit"}' \\
        [--action upload]   # adds action: upload to the entry
        [--force]           # overwrite if key already exists

Exits 1 if key exists and --force not given.
Exits 0 on success; prints: OK: wrote '<key>' to <path>

Notes:
  - The 'rationale' field from AI output is automatically stripped (not stored in yaml).
  - Creates parent directories if they don't exist.
  - Preserves existing keys and their ordering.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Append element to YAML elements file")
    parser.add_argument("--yaml", required=True, dest="yaml_file",
                        help="Path to elements yaml file")
    parser.add_argument("--key", required=True,
                        help="Element key, e.g. 'step3_提交按钮'")
    parser.add_argument("--spec", required=True,
                        help="JSON locator spec (rationale field is ignored)")
    parser.add_argument("--action", default=None,
                        help="Action override, e.g. 'upload'")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing key (default: refuse)")
    args = parser.parse_args()

    yaml_path = Path(args.yaml_file)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing content
    existing: dict = {}
    if yaml_path.exists():
        try:
            with yaml_path.open(encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"ERROR: could not read {yaml_path}: {e}", file=sys.stderr)
            sys.exit(1)

    if args.key in existing and not args.force:
        print(
            f"ERROR: key {args.key!r} already exists in {yaml_path}. "
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse spec; strip AI-only fields
    try:
        entry: dict = json.loads(args.spec)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in --spec: {e}", file=sys.stderr)
        sys.exit(1)

    entry.pop("rationale", None)  # AI annotation; not part of BasePage YAML format

    if args.action:
        entry["action"] = args.action

    existing[args.key] = entry

    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"OK: wrote {args.key!r} to {yaml_path}")


if __name__ == "__main__":
    main()
