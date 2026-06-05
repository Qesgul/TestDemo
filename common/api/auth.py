# -*- coding: utf-8 -*-
"""CAS API 登录助手 + storage_state 适配层。

CAS 三步流程（纯 API → 浏览器 callback）：
  1. POST /cas/v1/tickets  → 201 + TGT URL
  2. POST TGT_URL?service= → ST token
  3. browser.goto(service?ticket=ST) → JS 执行 → session cookie 落位

storage_state 格式：{"cookies": [...], "origins": []}
"""
import logging
from typing import Optional

from common.cookie_manager import CookieManager
from common.yaml_loader import load_yaml

logger = logging.getLogger(__name__)

_CAS_URL = "https://www.znzmo.com/cas/v1/tickets"
_SERVICE_URL = "https://www.znzmo.com/personalCenter"
# 服务端验活接口：GET 幂等无副作用，靠 body 的 errorCode 区分登录态
#   已登录: {"error":{"errorCode":"0",...},"data":11}
#   未登录: {"error":{"errorCode":"00005","errorMsg":"没有登录"},"data":null}
_VALIDATION_URL = "https://api.znzmo.com/payCenter/pay/userPayIdentity"
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def verify_session_alive(context) -> bool:
    """用浏览器 context 当前 cookie 调用验活接口，判断 session 是否仍有效。

    znzmo 限制同账号最多 2 个并发会话，第三个登录会踢掉最早的，
    导致本地 cookie 未过期但服务端 session 已失效。本地时间判断无法识别这种情况，
    须靠服务端接口确认。

    判定：error.errorCode == "0" → 有效；其余一切（非 200 / 解析失败 /
    网络异常 / 非 "0" 码）→ 视为失效返回 False（保守策略：宁可多登一次，
    不放过失效 cookie 导致用例假失败）。

    Args:
        context: Playwright BrowserContext（其 .request 复用 context 的 cookie jar）。
    """
    try:
        resp = context.request.get(_VALIDATION_URL, timeout=10000)
        if resp.status != 200:
            return False
        body = resp.json()
        return str(body.get("error", {}).get("errorCode", "")) == "0"
    except Exception as e:
        logger.warning("cookie 服务端验活异常（视为失效）: %s", e)
        return False


def _default_account() -> Optional[str]:
    """默认登录账号：取 tests/data/login_data.yaml cases[0].username（与 logged_in_context 一致）。"""
    data = load_yaml("tests/data/login_data.yaml") or {}
    cases = data.get("cases") or []
    if not cases:
        return None
    return cases[0].get("username")


def cas_login(playwright_instance, context, anchor_page, username: str, password: str) -> None:
    """CAS API 登录：TGT → ST → 浏览器 callback，跳过 UI 表单。

    优先复用 CookieManager 缓存的有效 cookie；若无效则走 CAS API 三步流程。
    登录完成后 anchor_page 停在 https://www.znzmo.com/（CAS callback 重定向结果）。
    如 API 登录失败，向上抛异常由调用方决定是否兜底 UI 登录。

    Args:
        playwright_instance: pytest-playwright 提供的 Playwright 对象（用于创建临时 APIRequestContext）。
        context: Playwright BrowserContext（cookie 将注入此 context）。
        anchor_page: 浏览器 session 激活页（callback URL 由此页面导航）。
        username: 手机号。
        password: 密码。
    """
    # ── Step 0: cookie 缓存（本地有效性 + 服务端验活）─────────────
    cookie_data = CookieManager.load_cookies(username)
    if cookie_data and CookieManager.is_cookie_valid(
        cookie_data, expected_account_identifier=username
    ):
        logger.info("账号 %s 发现本地有效 cookie，注入并做服务端验活", username)
        try:
            context.clear_cookies()
            CookieManager.set_cookies_to_context(context, cookie_data)
            if verify_session_alive(context):
                logger.info("账号 %s cookie 服务端验活通过，跳过 CAS 登录", username)
                anchor_page.goto(_SERVICE_URL, wait_until="domcontentloaded", timeout=20000)
                anchor_page.wait_for_timeout(500)
                return
            logger.warning(
                "账号 %s cookie 本地有效但服务端已失效（疑似被踢下线），重新走 CAS 登录",
                username,
            )
            context.clear_cookies()
        except Exception as e:
            logger.warning("cookie 注入/验活异常，回退 CAS API 登录: %s", e)

    # ── Step 1+2: TGT → ST（纯 HTTP，无浏览器）────────────────────
    logger.info("账号 %s 开始 CAS API 登录（TGT → ST）", username)
    api_ctx = playwright_instance.request.new_context(
        extra_http_headers={"User-Agent": _DESKTOP_UA}
    )
    try:
        r1 = api_ctx.post(_CAS_URL, form={"username": username, "password": password})
        if r1.status != 201:
            raise RuntimeError(f"CAS TGT 获取失败: HTTP {r1.status}")

        tgt_url = r1.headers.get("location", "").replace("http://", "https://")
        if not tgt_url:
            raise RuntimeError("CAS 响应缺少 Location header（TGT URL）")

        r2 = api_ctx.post(tgt_url, form={"service": _SERVICE_URL})
        st = r2.text().strip()
        if not st.startswith("ST-"):
            raise RuntimeError(f"CAS ST 获取失败（期望 ST- 开头）: {st[:80]}")

        logger.info("账号 %s CAS ST 获取成功: %s...", username, st[:30])
    finally:
        api_ctx.dispose()

    # ── Step 3: 浏览器 navigate → JS 执行 → session cookie 下发 ──
    callback_url = f"{_SERVICE_URL}?ticket={st}"
    logger.info("浏览器导航至 CAS callback URL")
    anchor_page.goto(callback_url, wait_until="domcontentloaded", timeout=20000)
    anchor_page.wait_for_timeout(2000)          # 等待 JS 完成 session 建立
    logger.info("账号 %s CAS 登录完成，当前 URL: %s", username, anchor_page.url)

    # ── Step 4: 保存 cookie ────────────────────────────────────────
    try:
        CookieManager.save_cookies(username, context)
        logger.info("账号 %s cookie 已保存", username)
    except Exception as e:
        logger.warning("cookie 保存失败（不影响本次登录）: %s", e)


def load_storage_state(account_identifier: Optional[str] = None) -> Optional[dict]:
    """返回 Playwright storage_state 或 None（无有效 cookie / 无账号）。

    Args:
        account_identifier: 账号标识（手机号）。None 时取默认账号。

    Returns:
        {"cookies": [...], "origins": []} 或 None。
    """
    account = account_identifier or _default_account()
    if not account:
        return None
    data = CookieManager.load_cookies(account)
    if not data or not CookieManager.is_cookie_valid(data):
        return None
    return {"cookies": data.get("cookies", []), "origins": []}
