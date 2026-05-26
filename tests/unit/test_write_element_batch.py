"""Unit tests for write_element batch mode."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "write_element.py"

# Force UTF-8 stdio in the child process (Windows defaults to cp936/cp1252
# which can't decode error messages containing non-ASCII clashing keys etc.)
_UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _run_batch(yaml_path: Path, batch_path: Path, extra_args: list[str] = None) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(SCRIPT),
        "--yaml", str(yaml_path),
        "--batch-json", str(batch_path),
    ] + (extra_args or [])
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=_UTF8_ENV)


def test_batch_writes_multiple_entries(tmp_path: Path) -> None:
    yaml_path = tmp_path / "out.yaml"
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps([
        {"key": "step1_提交", "spec": {"type": "css", "selector": "#submit"}},
        {"key": "step2_取消", "spec": {"type": "role", "role": "button", "name": "取消"}},
    ], ensure_ascii=False), encoding="utf-8")

    res = _run_batch(yaml_path, batch_path)
    assert res.returncode == 0, res.stderr
    assert "wrote 2 entries" in res.stdout

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert "step1_提交" in data
    assert data["step1_提交"]["selector"] == "#submit"
    assert "step2_取消" in data
    assert data["step2_取消"]["role"] == "button"


def test_batch_action_field_is_written(tmp_path: Path) -> None:
    yaml_path = tmp_path / "out.yaml"
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps([
        {"key": "step1_上传", "spec": {"type": "css", "selector": "input[type=file]"}, "action": "upload"},
    ], ensure_ascii=False), encoding="utf-8")

    res = _run_batch(yaml_path, batch_path)
    assert res.returncode == 0
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["step1_上传"]["action"] == "upload"


def test_batch_strips_rationale_from_spec(tmp_path: Path) -> None:
    yaml_path = tmp_path / "out.yaml"
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps([
        {"key": "step1", "spec": {"type": "css", "selector": "#x", "rationale": "best id"}},
    ], ensure_ascii=False), encoding="utf-8")

    _run_batch(yaml_path, batch_path)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert "rationale" not in data["step1"]


def test_batch_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    yaml_path = tmp_path / "out.yaml"
    yaml_path.write_text(yaml.safe_dump({"step1": {"type": "css", "selector": "#old"}}), encoding="utf-8")
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps([
        {"key": "step1", "spec": {"type": "css", "selector": "#new"}},
    ], ensure_ascii=False), encoding="utf-8")

    res = _run_batch(yaml_path, batch_path)
    assert res.returncode == 1
    assert "already exist" in res.stderr

    # confirm yaml unchanged
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["step1"]["selector"] == "#old"


def test_batch_with_force_overwrites(tmp_path: Path) -> None:
    yaml_path = tmp_path / "out.yaml"
    yaml_path.write_text(yaml.safe_dump({"step1": {"type": "css", "selector": "#old"}}), encoding="utf-8")
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps([
        {"key": "step1", "spec": {"type": "css", "selector": "#new"}},
    ], ensure_ascii=False), encoding="utf-8")

    res = _run_batch(yaml_path, batch_path, extra_args=["--force"])
    assert res.returncode == 0
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["step1"]["selector"] == "#new"


def test_legacy_single_spec_mode_still_works(tmp_path: Path) -> None:
    yaml_path = tmp_path / "out.yaml"
    cmd = [
        sys.executable, str(SCRIPT),
        "--yaml", str(yaml_path),
        "--key", "step1_x",
        "--spec", '{"type":"css","selector":"#y"}',
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["step1_x"]["selector"] == "#y"
