#!/usr/bin/env python
"""
Append one or many element entries to a YAML elements file.

Single-entry mode (legacy):
    python scripts/write_element.py \\
        --yaml pages/elements/my_elements.yaml \\
        --key "step3_提交按钮" \\
        --spec '{"type":"css","selector":"#OperationForm-btnSubmit"}' \\
        [--action upload] [--force]

Batch mode:
    python scripts/write_element.py \\
        --yaml pages/elements/my_elements.yaml \\
        --batch-json .planning/snapshot/step_1/to_write.json \\
        [--force]

Where to_write.json is:
    [
      {"key": "step1_提交", "spec": {"type":"css","selector":"#x"}},
      {"key": "step2_上传", "spec": {"type":"css","selector":"input[type=file]"}, "action": "upload"}
    ]

Exits 0 on success: "OK: wrote <N> entries to <path>"
Exits 1 if any key exists and --force not given (no partial writes).

Notes:
  - 'rationale' field in spec is auto-stripped before writing.
  - Creates parent directories if they don't exist.
  - Existing keys and ordering are preserved; new entries are appended.
  - Batch mode is atomic: validates all keys first, then writes once.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml


def _strip_rationale(spec: dict) -> dict:
    spec.pop("rationale", None)
    return spec


def _build_entry(spec: dict, action: str | None) -> dict:
    entry = _strip_rationale(dict(spec))  # copy
    if action:
        entry["action"] = action
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Append element(s) to YAML elements file")
    parser.add_argument("--yaml", required=True, dest="yaml_file",
                        help="Path to elements yaml file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--key", help="Element key (single-entry mode)")
    group.add_argument("--batch-json", dest="batch_json",
                       help="Path to JSON file containing [{key, spec, action?}, ...]")
    parser.add_argument("--spec", help="JSON locator spec (single-entry mode)")
    parser.add_argument("--action", default=None,
                        help="Action override, e.g. 'upload' (single-entry mode)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing keys (default: refuse)")
    args = parser.parse_args()

    # Build list of (key, spec, action) tuples for both modes
    pending: list[tuple[str, dict, str | None]] = []

    if args.key:
        if not args.spec:
            print("ERROR: --spec is required with --key", file=sys.stderr)
            sys.exit(1)
        try:
            spec_dict = json.loads(args.spec)
        except json.JSONDecodeError as e:
            print(f"ERROR: invalid JSON in --spec: {e}", file=sys.stderr)
            sys.exit(1)
        pending.append((args.key, spec_dict, args.action))
    else:
        try:
            batch = json.loads(Path(args.batch_json).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"ERROR: batch-json error: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(batch, list):
            print("ERROR: batch-json must be a JSON array", file=sys.stderr)
            sys.exit(1)
        for i, item in enumerate(batch):
            if not isinstance(item, dict) or "key" not in item or "spec" not in item:
                print(f"ERROR: batch item {i} must have 'key' and 'spec' fields", file=sys.stderr)
                sys.exit(1)
            pending.append((item["key"], item["spec"], item.get("action")))

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

    # Pre-flight: check all keys before writing anything (atomic)
    if not args.force:
        clashing = [k for k, _, _ in pending if k in existing]
        if clashing:
            print(
                f"ERROR: keys already exist in {yaml_path}: {clashing!r}. "
                "Use --force to overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Apply
    for key, spec_dict, action in pending:
        existing[key] = _build_entry(spec_dict, action)

    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    if len(pending) == 1:
        print(f"OK: wrote {pending[0][0]!r} to {yaml_path}")
    else:
        print(f"OK: wrote {len(pending)} entries to {yaml_path}")


if __name__ == "__main__":
    main()
