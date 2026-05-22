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
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

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

    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
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
