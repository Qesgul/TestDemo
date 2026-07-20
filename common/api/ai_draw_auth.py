# -*- coding: utf-8 -*-
"""AI 绘图专用登录模块。

解决从 su.znzmo.com 登录后导航到 ai.znzmo.cn 时弹窗/重定向干扰的问题。

策略：
  1. 优先复用 logged_in_context 的 .znzmo.cn 域 SESSION cookie
  2. cookie 无效时在 ai.znzmo.cn 页面内完成登录（不走 su.znzmo.com）
  3. 登录完成后验证 SESSION cookie 存在且服务端验活通过

适用场景：AI 绘图相关测试（定价采集、Agent 模式等）。
"""
from __future__ import annotations

import logging
from typing import Optional

from playwright.sync_api import Page

from common.selector_finder.login_session import reload_dismiss_popups

# Runtime rule: ai.znzmo.cn owns an independent auth profile/storage_state.
# Do not reuse material-site logged_in_context or .znzmo.com cookies here.
_log = logging.getLogger(__name__)

# AI 绘图首页（非 agent 模式，登录态入口在此页）
_AI_DRAW_HOME = "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=home"

# 服务端验活接口（复用 auth.py 中的同一接口）
_VALIDATION_URL = "https://api.znzmo.com/payCenter/pay/userPayIdentity"

# 登录态标识：知币余额元素可见即已登录
_LOGGED_IN_SELECTOR = '[class*="zidianAmount"]'


def login_ai_draw(page: Page, username: str, password: str) -> bool:
    """在 ai.znzmo.cn 页面内完成登录。

    流程：
      1. 打开 ai.znzmo.cn/community/AIDrawPage.html?menuKey=home
      2. 检测是否已登录（知币余额元素可见）
      3. 如未登录：点击登录入口 → 手机 tab → 账号密码登录 → 填手机号 → 填密码 → 提交
      4. 等待登录完成，验证 SESSION cookie 存在

    Args:
        page: Playwright Page 对象（需属于目标 BrowserContext）。
        username: 手机号。
        password: 密码。

    Returns:
        True 表示登录成功；False 表示失败。
    """
    _log.info("AI 绘图登录：导航到 ai.znzmo.cn 首页")
    page.goto(_AI_DRAW_HOME, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(3000)

    # 检测是否已登录
    if _is_logged_in(page):
        _log.info("AI 绘图页面已处于登录态，跳过登录")
        return True

    _log.info("AI 绘图页面未登录，开始页面内登录流程")

    # 弹窗绕过
    reload_dismiss_popups(page)

    # 点击登录入口
    opened = False
    for sel in [
        "#loginsuccessnews",
        ".AIpublicHeader__loginWrapper__QSXAF",
        '[class*="loginWrapper"]',
        '[class*="LoginWrapper"]',
        'text=登录',
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
        _log.warning("ai_draw_login: 未找到登录入口")
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
                el.fill(username)
                filled_user = True
                break
        except Exception:
            continue
    if not filled_user:
        _log.warning("ai_draw_login: 未找到手机号输入框")
        return False

    # 密码输入框
    filled_pwd = False
    for sel in ['input[type="password"]', 'input[placeholder*="密码"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.fill(password)
                filled_pwd = True
                break
        except Exception:
            continue
    if not filled_pwd:
        _log.warning("ai_draw_login: 未找到密码输入框")
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

    success = _is_logged_in(page)
    if success:
        # 验证 SESSION cookie 存在
        cookies = page.context.cookies("https://ai.znzmo.cn")
        session_cookie = any(c["name"] == "SESSION" for c in cookies)
        if not session_cookie:
            _log.warning("ai_draw_login: 登录态标识可见但 SESSION cookie 不存在")
            success = False
        else:
            _log.info("ai_draw_login: 登录成功，SESSION cookie 已建立")
    else:
        _log.warning("ai_draw_login: 登录失败（登录态标识不可见）")

    return success


def verify_ai_draw_session(context) -> bool:
    """验证 ai.znzmo.cn 的 SESSION 是否有效。

    调用 https://api.znzmo.com/payCenter/pay/userPayIdentity 验证。

    Args:
        context: Playwright BrowserContext（其 .request 复用 context 的 cookie jar）。

    Returns:
        True 表示 session 有效；False 表示无效。
    """
    try:
        resp = context.request.get(_VALIDATION_URL, timeout=10_000)
        if resp.status != 200:
            return False
        body = resp.json()
        return str(body.get("error", {}).get("errorCode", "")) == "0"
    except Exception as e:
        _log.warning("AI 绘图 session 验活异常（视为失效）: %s", e)
        return False


def _is_logged_in(page: Page) -> bool:
    """检测 AI 绘图页面是否已登录。

    判断依据：知币余额元素（zidianAmount）可见。
    """
    try:
        el = page.locator(_LOGGED_IN_SELECTOR).first
        return el.is_visible(timeout=3000)
    except Exception:
        return False
