# -*- coding: utf-8 -*-
"""Verify auth profile routing and optional storage_state warmup.

Default mode is dry-run and has no browser/login side effects. Use --login only
when you intentionally want to warm up target-site storage_state files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.auth_session import load_default_account, resolve_auth_profile, state_path_for

TARGETS = {
    "material": "https://su.znzmo.com/sumoxing/1200607583.html",
    "ai_draw": "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=home",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true", help="warm up storage_state with real UI login")
    parser.add_argument("--headless", action="store_true", help="run browser in headless mode when --login is used")
    parser.add_argument("--user", default=None, help="override login username")
    parser.add_argument("--password", default=None, help="override login password")
    args = parser.parse_args()

    account = load_default_account() or {}
    username = args.user or account.get("username")
    password = args.password or account.get("password")
    rows = []

    for label, url in TARGETS.items():
        profile = resolve_auth_profile(url)
        row = {
            "target": label,
            "url": url,
            "profile": profile.name,
            "scope": profile.scope,
            "cache_path": str(state_path_for(url, username or "missing")),
        }
        rows.append(row)

    if args.login:
        if not username or not password:
            raise RuntimeError("Missing account credentials; provide --user/--password or account_pool.yaml")
        from common.selector_finder.login_session import ensure_storage_state

        for row in rows:
            row["warmed_state"] = ensure_storage_state(
                row["url"],
                username,
                password,
                headless=args.headless,
            )

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
