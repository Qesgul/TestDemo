#!/usr/bin/env python
"""
Verify a single locator spec against a live page.

Usage:
    python scripts/verify_locator.py \\
        --url https://example.com \\
        --spec '{"type":"role","role":"button","name":"提交","exact":true}' \\
        [--browser chromium]

Stdout (JSON):
    {"unique": true,  "count": 1, "visible": true,  "error": null}
    {"unique": false, "count": 3, "visible": true,  "error": null}
    {"unique": false, "count": 0, "visible": false, "error": "TimeoutError: ..."}

Spec format examples:
    {"type": "role",        "role": "button", "name": "提交", "exact": true}
    {"type": "css",         "selector": "#OperationForm-btnSubmit"}
    {"type": "text",        "text": "家装", "exact": true}
    {"type": "label",       "label": "用户名", "exact": false}
    {"type": "placeholder", "placeholder": "请输入关键词"}
    {"type": "test_id",     "test_id": "submit-btn"}
    {"type": "css",         "selector": "input[type=\\"file\\"]", "scope": "#uploadWrapper"}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from common.selector_finder.verifier import build_locator
from common.selector_finder.yaml_reuse import _yaml_dict_to_spec  # reuse existing parser


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a locator spec on a live page")
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--spec", required=True, help="JSON locator spec (single object)")
    parser.add_argument(
        "--browser", default="chromium",
        choices=["chromium", "firefox", "webkit"],
    )
    args = parser.parse_args()

    try:
        spec_dict = json.loads(args.spec)
    except json.JSONDecodeError as e:
        print(json.dumps({"unique": False, "count": 0, "visible": False,
                          "error": f"invalid JSON: {e}"}))
        return

    spec = _yaml_dict_to_spec(spec_dict)
    if spec is None:
        print(json.dumps({"unique": False, "count": 0, "visible": False,
                          "error": "could not parse spec into LocatorSpec"}))
        return

    result: dict = {"unique": False, "count": 0, "visible": False, "error": None}

    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch(headless=True)
        page = browser.new_context().new_page()
        page.set_default_timeout(8_000)
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_timeout(1_500)
            locator = build_locator(page, spec)
            count = locator.count()
            result["count"] = count
            if count == 1:
                result["unique"] = True
                try:
                    result["visible"] = locator.first.is_visible()
                except Exception:
                    result["visible"] = False
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        finally:
            browser.close()

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
