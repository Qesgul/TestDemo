# -*- coding: utf-8 -*-
"""Login-state reuse helpers for selector/debug Playwright sessions.

The important rule is simple: resolve the target URL to an auth profile, reuse
only that profile's cached storage_state, verify it on the target site, and try
UI login at most once when the cache is missing or invalid.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from common.auth_session import DEFAULT_AUTH_DIR, resolve_auth_profile, state_path_for

_log = logging.getLogger(__name__)
_DEFAULT_AUTH_DIR = DEFAULT_AUTH_DIR


def reload_dismiss_popups(page, max_reloads: int = 3) -> None:
    """Bypass non-target blocking Ant Design modals by reloading a few times."""
    for i in range(max_reloads):
        try:
            blocking = page.locator(".ant-modal-wrap, .ant-modal-mask").first
            if not blocking.is_visible(timeout=1500):
                return
            _log.debug("dismiss_popup round %d: blocking modal -> reload", i)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
        except Exception:
            return


def is_logged_in(page) -> bool:
    """Backward-compatible generic check, now conservative on unknown pages."""
    try:
        entry = page.locator("#loginsuccessnews")
        if entry.count() > 0:
            return not entry.first.is_visible(timeout=1500)
        login_modal = page.locator('[class*="LoginModal__loginModalContainer__"]')
        if login_modal.count() > 0:
            return not login_modal.first.is_visible(timeout=1500)
        return False
    except Exception:
        return False


def is_ai_draw_logged_in(page) -> bool:
    try:
        if page.get_by_text("登录|注册有礼", exact=True).is_visible(timeout=3000):
            return False
        return page.locator('[class*="zidianAmount"]').first.is_visible(timeout=3000)
    except Exception:
        return False


def is_material_logged_in(page) -> bool:
    try:
        login_modal = page.locator('[class*="LoginModal__loginModalContainer__"]')
        if login_modal.count() > 0:
            return not login_modal.first.is_visible(timeout=1500)
        entry = page.locator("#loginsuccessnews")
        if entry.count() > 0:
            return not entry.first.is_visible(timeout=1500)
        return False
    except Exception:
        return False


def verify_target_login(page, url: str) -> bool:
    profile = resolve_auth_profile(url)
    if profile.name == "ai_draw":
        return is_ai_draw_logged_in(page)
    if profile.name == "material":
        return is_material_logged_in(page)
    return False


def znzmo_ui_login(page, user: str, pwd: str) -> bool:
    """Run the standard Znzmo account/password login flow on the current site."""
    reload_dismiss_popups(page)

    opened = False
    for sel in [
        "#loginsuccessnews",
        ".AIpublicHeader__loginWrapper__QSXAF",
        '[class*="loginWrapper"]',
        '[class*="LoginWrapper"]',
        '[class*="login"]',
        "text=登录",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(force=True)
                page.wait_for_timeout(1500)
                opened = True
                break
        except Exception:
            continue

    if not opened:
        try:
            entry = page.get_by_text("登录|注册有礼", exact=True)
            if entry.is_visible(timeout=2000):
                entry.click()
                page.wait_for_timeout(1500)
                opened = True
        except Exception:
            pass

    if not opened:
        # Some material pages show LoginModal automatically.
        try:
            opened = page.locator('[class*="LoginModal__loginModalContainer__"]').first.is_visible(timeout=1500)
        except Exception:
            opened = False
    if not opened:
        _log.warning("znzmo_ui_login: login entry not found")
        return False

    for label in ["手机", "账号密码登录", "密码登录"]:
        try:
            tab = page.locator(f"text={label}").first
            if tab.is_visible(timeout=1200):
                tab.click()
                page.wait_for_timeout(400)
        except Exception:
            continue

    filled_user = False
    for sel in ['input[placeholder*="手机"]', 'input[placeholder*="账号"]', 'input[type="text"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.fill(user)
                filled_user = True
                break
        except Exception:
            continue
    if not filled_user:
        _log.warning("znzmo_ui_login: username input not found")
        return False

    filled_pwd = False
    for sel in ['input[type="password"]', 'input[placeholder*="密码"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.fill(pwd)
                filled_pwd = True
                break
        except Exception:
            continue
    if not filled_pwd:
        _log.warning("znzmo_ui_login: password input not found")
        return False

    clicked = False
    for sel in [
        '[class*="login-btn"]',
        '[class*="loginBtn"]',
        '[class*="Accountpassword"] button',
        'button:has-text("登录")',
        "text=登录",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        _log.warning("znzmo_ui_login: submit button not found")
        return False

    page.wait_for_timeout(4000)
    reload_dismiss_popups(page)
    success = is_logged_in(page) or is_ai_draw_logged_in(page)
    _log.info("znzmo_ui_login: %s", "success" if success else "failed")
    return success


def _state_filename(url: str) -> str:
    """Legacy helper kept for callers/tests that import it directly."""
    domain = urlparse(url).netloc or re.sub(r"[^\w]", "_", url[:40])
    safe = re.sub(r"[^\w]", "_", domain).strip("_")
    return f"{safe}_state.json"


def ensure_storage_state(
    url: str,
    user: Optional[str],
    pwd: Optional[str],
    *,
    state_dir: Optional[Path] = None,
    headless: bool = True,
    max_age_hours: float = 12,
) -> Optional[str]:
    """Return a verified target-site storage_state path.

    The cache key includes auth profile + account. A failed UI login raises once
    instead of retrying, which prevents selector/debug agents from login loops.
    """
    if not user or not pwd:
        return None

    profile = resolve_auth_profile(url)
    auth_dir = state_dir or _DEFAULT_AUTH_DIR
    auth_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_path_for(url, user, state_dir=auth_dir)

    from playwright.sync_api import sync_playwright

    if state_path.exists():
        age_hours = (time.time() - state_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            _log.info("Found cached %s storage_state: %s", profile.name, state_path)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=headless)
                ctx = browser.new_context(
                    storage_state=str(state_path),
                    viewport={"width": 1366, "height": 900},
                )
                page = ctx.new_page()
                page.set_default_timeout(15_000)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(1500)
                    if verify_target_login(page, url):
                        _log.info("Reused verified %s storage_state", profile.name)
                        return str(state_path)
                    _log.info("Cached %s storage_state failed target verification", profile.name)
                finally:
                    ctx.close()
                    browser.close()
        else:
            _log.info("storage_state expired (%.1fh > %.1fh): %s", age_hours, max_age_hours, state_path)

    _log.info("Login once for %s and save storage_state -> %s", profile.name, state_path)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(15_000)
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3000)

        if not verify_target_login(page, url):
            ok = znzmo_ui_login(page, user, pwd)
            if not ok or not verify_target_login(page, url):
                ctx.close()
                browser.close()
                raise RuntimeError(f"Login failed for auth profile {profile.name}; stop retrying")

        ctx.storage_state(path=str(state_path))
        ctx.close()
        browser.close()

    _log.info("storage_state saved: %s", state_path)
    return str(state_path)
