#!/usr/bin/env python
"""
Capture page a11y tree + screenshot for Claude-driven selector analysis.

Uses Playwright's aria_snapshot() (>= 1.46) which returns a YAML string
describing the accessibility tree — ideal for Claude to read and analyze.

Usage:
    python scripts/capture_snapshot.py \\
        --url https://example.com \\
        --out .planning/snapshot/ \\
        [--focus "上传"]          # keyword -> triggers scene_hooks
        [--browser chromium]

Outputs (in <out>/):
    a11y.yaml      ARIA accessibility tree (YAML text)
    screenshot.png 1280x800 viewport screenshot
    meta.json      { url, timestamp, viewport, focus_kw }
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from common.selector_finder.login_session import ensure_storage_state
from common.selector_finder.models import ExtractedStep
from common.selector_finder.scene_hooks import apply_hooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture page snapshot for AI selector")
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--out", default=".planning/snapshot", help="Output directory")
    parser.add_argument("--focus", default="", help="Keyword for scene hooks (e.g. '上传')")
    parser.add_argument(
        "--browser", default="chromium",
        choices=["chromium", "firefox", "webkit"],
    )
    parser.add_argument(
        "--cookies", default=None,
        help="Path to cookies JSON file (same format as common/cookies_dev_*.json)",
    )
    parser.add_argument(
        "--storage-state", default=None, dest="storage_state",
        help="Path to Playwright storage_state JSON (cookies + localStorage)；优先于 --cookies",
    )
    parser.add_argument(
        "--login-user", default=os.environ.get("CAPTURE_LOGIN_USER"),
        dest="login_user",
        help="登录用户名（也可通过 CAPTURE_LOGIN_USER 环境变量传入）",
    )
    parser.add_argument(
        "--login-pwd", default=os.environ.get("CAPTURE_LOGIN_PWD"),
        dest="login_pwd",
        help="登录密码（也可通过 CAPTURE_LOGIN_PWD 环境变量传入）",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build a fake ExtractedStep so scene_hooks can read .description / .element_desc
    fake_step = ExtractedStep(
        step_index=0,
        description=args.focus,
        action="click",
        element_desc=args.focus,
    )

    # 优先 storage_state（含 cookies + localStorage）；若提供了凭据则自动完成首次登录并缓存
    state_path = args.storage_state or ensure_storage_state(
        args.url, args.login_user, args.login_pwd
    )

    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch(headless=True)

        ctx_kwargs: dict = {"viewport": {"width": 1280, "height": 800}}
        if state_path:
            ctx_kwargs["storage_state"] = state_path
            _log.info("Using storage_state: %s", state_path)
        ctx = browser.new_context(**ctx_kwargs)

        # 旧式 cookies 注入（无 storage_state 时的兜底）
        if args.cookies and not state_path:
            raw = json.loads(Path(args.cookies).read_text(encoding="utf-8"))
            cookie_list = raw if isinstance(raw, list) else raw.get("cookies", [])
            pw_fields = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
            clean = [{k: v for k, v in c.items() if k in pw_fields} for c in cookie_list]
            ctx.add_cookies(clean)
            _log.info("Injected %d cookies from %s", len(clean), args.cookies)

        page = ctx.new_page()
        page.set_default_timeout(15_000)

        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)

        apply_hooks(page, fake_step)

        # a11y tree — aria_snapshot() returns YAML string (Playwright >= 1.46)
        aria_yaml = page.aria_snapshot() or ""
        (out_dir / "a11y.yaml").write_text(aria_yaml, encoding="utf-8")

        # screenshot
        page.screenshot(path=str(out_dir / "screenshot.png"), full_page=False)

        # meta
        meta = {
            "url": args.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "viewport": {"width": 1280, "height": 800},
            "focus_kw": args.focus,
        }
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        browser.close()

    _log.info("Snapshot saved to %s", out_dir)
    print(f"OK: {out_dir}/a11y.yaml + screenshot.png + meta.json")


if __name__ == "__main__":
    main()
