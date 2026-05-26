#!/usr/bin/env python
"""
Verify locator spec(s) against a live page.

Single-spec mode (legacy, for debugging):
    python scripts/verify_locator.py \\
        --url https://example.com \\
        --spec '{"type":"role","role":"button","name":"提交","exact":true}'

Batch mode (preferred for AI selector workflow):
    python scripts/verify_locator.py \\
        --url https://example.com \\
        --specs-json .planning/snapshot/step_1/candidates.json

Where candidates.json is:
    [
      {"key": "step1_提交按钮", "spec": {"type": "role", "role": "button", "name": "提交"}},
      {"key": "step2_上传按钮", "spec": {"type": "css", "selector": "input[type=file]"}}
    ]

Stdout (batch mode JSON):
    [
      {"key": "step1_提交按钮", "unique": true,  "count": 1, "visible": true,  "error": null},
      {"key": "step2_上传按钮", "unique": false, "count": 0, "visible": false, "error": null}
    ]

Stdout (single-spec mode, unchanged):
    {"unique": true, "count": 1, "visible": true, "error": null}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import Page, sync_playwright

from common.selector_finder.verifier import build_locator
from common.selector_finder.yaml_reuse import _yaml_dict_to_spec


def _verify_one(page: Page, spec_dict: dict) -> dict:
    """Run a single spec against the given page; return the result row."""
    result = {"unique": False, "count": 0, "visible": False, "error": None}
    spec = _yaml_dict_to_spec(spec_dict)
    if spec is None:
        result["error"] = "could not parse spec into LocatorSpec"
        return result
    try:
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
    return result


def verify_specs(page: Page, specs: list[dict]) -> list[dict]:
    """
    Verify many specs against one page.

    Args:
        page: Playwright Page (already navigated)
        specs: list of {"key": str, "spec": dict}

    Returns:
        list of {"key": str, "unique": bool, "count": int, "visible": bool, "error": str|None}
        in the same order as input.
    """
    results: list[dict] = []
    for item in specs:
        key = item.get("key", "")
        spec_dict = item.get("spec", {})
        row = _verify_one(page, spec_dict)
        # 重排字段顺序：key 在最前面
        ordered = {"key": key, "unique": row["unique"], "count": row["count"],
                   "visible": row["visible"], "error": row["error"]}
        results.append(ordered)
    return results


def _load_cookies(ctx, cookies_path: str) -> None:
    raw = json.loads(Path(cookies_path).read_text(encoding="utf-8"))
    cookie_list = raw if isinstance(raw, list) else raw.get("cookies", [])
    pw_fields = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    clean = [{k: v for k, v in c.items() if k in pw_fields} for c in cookie_list]
    ctx.add_cookies(clean)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify locator spec(s) on a live page")
    parser.add_argument("--url", required=True, help="Target page URL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--spec", help="Single JSON locator spec (legacy mode)")
    group.add_argument("--specs-json", dest="specs_json",
                       help="Path to JSON file containing [{key, spec}, ...] (batch mode)")
    parser.add_argument("--browser", default="chromium",
                        choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--cookies", default=None,
                        help="Path to cookies JSON file")
    args = parser.parse_args()

    # Parse input first to fail fast
    if args.spec:
        try:
            specs = [{"key": "_single", "spec": json.loads(args.spec)}]
        except json.JSONDecodeError as e:
            print(json.dumps({"unique": False, "count": 0, "visible": False,
                              "error": f"invalid JSON: {e}"}, ensure_ascii=False))
            return
    else:
        try:
            specs = json.loads(Path(args.specs_json).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(json.dumps([{"key": "_load", "unique": False, "count": 0,
                               "visible": False, "error": f"specs-json error: {e}"}],
                             ensure_ascii=False))
            return
        if not isinstance(specs, list):
            print(json.dumps([{"key": "_load", "unique": False, "count": 0,
                               "visible": False, "error": "specs-json must be a JSON array"}],
                             ensure_ascii=False))
            return

    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch(headless=True)
        ctx = browser.new_context()
        if args.cookies:
            _load_cookies(ctx, args.cookies)
        page = ctx.new_page()
        page.set_default_timeout(8_000)
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_timeout(1_500)
            results = verify_specs(page, specs)
        finally:
            browser.close()

    if args.spec:
        # Legacy single-spec mode: strip the key wrapper
        row = results[0]
        out = {"unique": row["unique"], "count": row["count"],
               "visible": row["visible"], "error": row["error"]}
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
