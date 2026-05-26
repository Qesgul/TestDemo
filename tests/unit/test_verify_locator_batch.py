"""Unit tests for verify_locator batch helper."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

# 让 import 找到 scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from verify_locator import verify_specs  # type: ignore[import-not-found]


@pytest.fixture(scope="module")
def page():
    """A Playwright page loaded with controlled HTML for assertions."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        p = ctx.new_page()
        p.set_content("""
        <html>
          <body>
            <button id="btn-submit">提交</button>
            <button>提交</button>
            <input type="file" id="upload-input"/>
            <div role="dialog" aria-label="弹窗"><span>内容</span></div>
          </body>
        </html>
        """)
        yield p
        browser.close()


def test_empty_specs_returns_empty_list(page) -> None:
    assert verify_specs(page, []) == []


def test_unique_spec_returns_unique_true(page) -> None:
    results = verify_specs(page, [
        {"key": "step1_submit_id", "spec": {"type": "css", "selector": "#btn-submit"}},
    ])
    assert len(results) == 1
    assert results[0]["key"] == "step1_submit_id"
    assert results[0]["unique"] is True
    assert results[0]["count"] == 1


def test_duplicate_spec_returns_unique_false_count_gt_1(page) -> None:
    results = verify_specs(page, [
        {"key": "step1_two_buttons", "spec": {"type": "role", "role": "button", "name": "提交"}},
    ])
    assert results[0]["unique"] is False
    assert results[0]["count"] == 2


def test_missing_spec_returns_count_0(page) -> None:
    results = verify_specs(page, [
        {"key": "step1_missing", "spec": {"type": "css", "selector": "#does-not-exist"}},
    ])
    assert results[0]["unique"] is False
    assert results[0]["count"] == 0


def test_mixed_batch_returns_all_results_in_order(page) -> None:
    results = verify_specs(page, [
        {"key": "a", "spec": {"type": "css", "selector": "#btn-submit"}},        # unique
        {"key": "b", "spec": {"type": "css", "selector": "#does-not-exist"}},    # missing
        {"key": "c", "spec": {"type": "role", "role": "button", "name": "提交"}},  # duplicate
    ])
    assert [r["key"] for r in results] == ["a", "b", "c"]
    assert results[0]["unique"] is True
    assert results[1]["count"] == 0
    assert results[2]["count"] == 2


def test_invalid_spec_returns_error_field(page) -> None:
    results = verify_specs(page, [
        {"key": "bad", "spec": {"type": "nonexistent_strategy"}},
    ])
    assert results[0]["unique"] is False
    assert results[0]["error"] is not None
