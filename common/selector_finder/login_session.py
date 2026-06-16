"""
跨域登录态复用工具——解决抓取场景反复登录问题。

策略：
  1. 检测 .auth/<domain>_state.json 是否存在且新鲜（max_age_hours）。
  2. 已有新鲜 state → 直接返回路径；调用方用 new_context(storage_state=path) 免登录。
  3. 无 state / 已过期 → 启动浏览器做一次 UI 登录，保存 storage_state 后返回路径。
  4. 无凭据（user/pwd 均为 None）→ 返回 None，调用方降级为匿名上下文（原有行为）。

弹窗处理规则（用户指引 2026-06-15）：
  非校验目标的阻塞弹窗（.ant-modal-wrap / .ant-modal-mask）一律 reload 绕过，
  不死磕关闭按钮，最多 reload max_reloads 次。
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

_log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_AUTH_DIR = _PROJECT_ROOT / ".auth"


# ── 弹窗绕过 ──────────────────────────────────────────────────────────────────

def reload_dismiss_popups(page, max_reloads: int = 3) -> None:
    """检测到阻塞 ant-modal 就 reload 绕过，最多 max_reloads 次。"""
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


# ── 登录态检测 ─────────────────────────────────────────────────────────────────

def is_logged_in(page) -> bool:
    """登录态判定：同时兼容 www/ai 站（#loginsuccessnews）和 su/sgt 站（LoginModal）。

    - www.znzmo.com / ai.znzmo.cn：「登录」入口 #loginsuccessnews 不可见即已登录
    - su.znzmo.com / sgt.znzmo.com 等子站：无 #loginsuccessnews，
      改为检测 LoginModal__loginModalContainer__ 是否可见（可见=未登录）
    """
    try:
        entry = page.locator("#loginsuccessnews")
        if entry.count() > 0:
            return not entry.first.is_visible(timeout=1500)
        # 无 #loginsuccessnews 时（su/sgt 子站），改检测登录弹窗容器
        login_modal = page.locator('[class*="LoginModal__loginModalContainer__"]')
        if login_modal.count() > 0:
            return not login_modal.first.is_visible(timeout=1500)
        return True
    except Exception:
        return True


# ── 知末 UI 登录流程 ───────────────────────────────────────────────────────────

def znzmo_ui_login(page, user: str, pwd: str) -> bool:
    """
    在当前页面执行知末网账号密码登录。

    前提：页面已导航到目标站，登录入口可见（或弹窗阻塞后 reload 已完成）。
    适用：ai.znzmo.cn 等与 www.znzmo.com 不共享 CAS session 的子站。

    返回：登录成功为 True，否则为 False。
    """
    reload_dismiss_popups(page)

    # 点击登录入口
    opened = False
    for sel in ["#loginsuccessnews", ".AIpublicHeader__loginWrapper__QSXAF"]:
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
        _log.warning("znzmo_ui_login: 未找到登录入口，跳过")
        return False

    # 知末标准弹窗：手机 tab → 账号密码登录（/ 密码登录）→ 填手机 → 填密码 → 提交
    for label in ["手机", "账号密码登录", "密码登录"]:
        try:
            t = page.locator(f"text={label}").first
            if t.is_visible(timeout=1200):
                t.click()
                page.wait_for_timeout(400)
        except Exception:
            continue

    # 手机号输入框
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
        _log.warning("znzmo_ui_login: 未找到手机号输入框")
        return False

    # 密码输入框
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
        _log.warning("znzmo_ui_login: 未找到密码输入框")
        return False

    # 提交按钮
    for sel in [
        '[class*="login-btn"]', '[class*="loginBtn"]',
        '[class*="Accountpassword"] button', 'button:has-text("登录")',
        'text=登录',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.click()
                break
        except Exception:
            continue

    page.wait_for_timeout(4000)
    reload_dismiss_popups(page)
    success = is_logged_in(page)
    _log.info("znzmo_ui_login: %s", "登录成功" if success else "登录失败（可能需检查凭据）")
    return success


# ── storage_state 复用入口 ─────────────────────────────────────────────────────

def _state_filename(url: str) -> str:
    """将 URL domain 转为合法文件名，例如 ai.znzmo.cn → ai_znzmo_cn_state.json。"""
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
    """
    确保 url 对应站点的登录 storage_state 文件存在且新鲜。

    Args:
        url: 目标站点 URL（用于推导 state 文件名 + 首次登录导航目标）。
        user: 登录用户名；为 None 时直接返回 None（匿名降级）。
        pwd:  登录密码；为 None 时直接返回 None（匿名降级）。
        state_dir: state 文件存放目录，默认为 <project_root>/.auth/。
        headless: 首次登录时是否 headless（默认 True）。
        max_age_hours: state 文件超过此时长视为过期，重新登录（默认 12h）。

    Returns:
        state JSON 文件的绝对路径字符串；无凭据时返回 None。
    """
    if not user or not pwd:
        return None

    auth_dir = state_dir or _DEFAULT_AUTH_DIR
    auth_dir.mkdir(parents=True, exist_ok=True)

    state_path = auth_dir / _state_filename(url)

    # 检查缓存是否新鲜
    if state_path.exists():
        age_hours = (time.time() - state_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            _log.info("复用已有 storage_state（%.1fh 前保存）: %s", age_hours, state_path)
            return str(state_path)
        _log.info("storage_state 已过期（%.1fh > %.0fh），重新登录", age_hours, max_age_hours)

    # 首次登录，保存 state
    _log.info("首次登录 %s，保存 storage_state → %s", url, state_path)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(15_000)
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3000)

        if not is_logged_in(page):
            znzmo_ui_login(page, user, pwd)

        ctx.storage_state(path=str(state_path))
        ctx.close()
        browser.close()

    _log.info("storage_state 已保存: %s", state_path)
    return str(state_path)
