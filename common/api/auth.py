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

# 需要额外建立本地 session 的子域列表（www 已由 cas_login 主流程覆盖）。
# Playwright new_context ≈ 无痕模式，第三方 cookie 受限，CAS SSO 无法跨域静默登录；
# establish_subdomain_sessions 显式对每个子域签 ST、page.goto callback 渲染页面执行 JS，
# 把 session 完整落进 context（JS 侧 localStorage/sessionStorage 亦需要执行才能初始化）。
#
# ⚠️ service URL 选型原则：选对应子域的「轻量页面」——CAS 白名单放行整个子域时任意路径均可，
#   但应避免重型素材详情页（3D 模型 WebGL 渲染在 headed 模式耗时极长）。
#   3d 子域用列表/分类页（无 3D 预览）；su 子域仍用已验证的素材详情页。
_SUBDOMAIN_SERVICES = [
    "https://su.znzmo.com/sumoxing/1200607583.html",
    "https://3d.znzmo.com/3dmoxing/",           # 3d 列表页：轻量，无 WebGL 3D 预览
]
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


def establish_subdomain_sessions(
    playwright_instance,
    context,
    page,
    username: str,
    password: str,
    services: Optional[list] = None,
) -> None:
    """用同一新鲜 TGT 对各子域签 ST + page.goto callback 渲染页面，建立各子域本地 session。

    解决 Playwright new_context（等价无痕模式）下第三方 cookie 受限、CAS SSO 无法
    自动静默跨子域登录的问题。

    必须用真实页面渲染（page.goto）而非纯 HTTP（context.request.get）原因：
    知末各子域在 CAS 回调时除写入 HTTP cookie 外，还通过 JavaScript 初始化 localStorage /
    sessionStorage 令牌或异步鉴权接口；纯 API 请求跳过 JS 执行，导致浏览器侧仍未登录。

    service URL 选型：选各子域的「轻量页面」避免重型渲染超时：
      - su：已验证的素材详情页（加载合理）
      - 3d：列表/分类页（无 WebGL 3D 模型预览，比素材详情页快数倍）

    验证（2026-06-16）：知末 CAS 白名单放行 su / 3d，三子域全部一次性覆盖。

    Args:
        playwright_instance: pytest-playwright 提供的 Playwright 对象（用于纯 API TGT/ST）。
        context: Playwright BrowserContext（session cookie 将落入此 context）。
        page: 执行 goto callback 的页面（通常为 anchor_page）。
        username: 手机号。
        password: 密码。
        services: 子域 service URL 列表；None 时使用模块默认 _SUBDOMAIN_SERVICES。
    """
    targets = _SUBDOMAIN_SERVICES if services is None else services
    if not targets:
        return

    logger.info("开始为 %d 个子域建立 session（CAS 回调 via page.goto + JS 渲染）", len(targets))
    api_ctx = playwright_instance.request.new_context(
        extra_http_headers={"User-Agent": _DESKTOP_UA}
    )
    try:
        r1 = api_ctx.post(_CAS_URL, form={"username": username, "password": password})
        if r1.status != 201:
            logger.warning("子域 session 建立失败：TGT 请求返回 HTTP %s，跳过", r1.status)
            return
        tgt_url = r1.headers.get("location", "").replace("http://", "https://")
        if not tgt_url:
            logger.warning("子域 session 建立失败：TGT 响应缺少 Location header")
            return

        for svc in targets:
            try:
                r2 = api_ctx.post(tgt_url, form={"service": svc})
                st = r2.text().strip()
                if not st.startswith("ST-"):
                    logger.warning("子域 %s：ST 获取失败（%r…），跳过", svc, st[:40])
                    continue
                callback_url = f"{svc}?ticket={st}"
                # page.goto 渲染页面：DOMContentLoaded 后 JS 已执行，session 完整落位。
                # 用轻量 service URL 避免 headed 模式下重型页面超时。
                page.goto(callback_url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(1000)
                final_url = page.url
                low = final_url.lower()
                if "login" in low or "/cas/" in low:
                    logger.warning(
                        "子域 %s：回调后落点=%s，疑似未建立 session（重定向到登录页）",
                        svc, final_url,
                    )
                    continue
                logger.info("子域 session 已建立: %s（落点: %s）", svc, final_url)
            except Exception as e:
                logger.warning("子域 %s session 建立失败（不影响其余子域）: %s", svc, e)
    finally:
        api_ctx.dispose()


_SU_LOGIN_TRIGGER_URL = "https://su.znzmo.com/sumoxing/1200607583.html"


def ui_login_via_su(page, username: str, password: str) -> bool:
    """在 su.znzmo.com 通过自动弹出的 LoginModal 做 UI 登录。

    su.znzmo.com 未登录时自动弹出 LoginModal，无需额外点击入口。
    登录成功后 .znzmo.com 域 session cookie 对 su/3d/www/sgt 等所有子域生效。

    CAS 已确认失效（2026-06-16 验证），此函数为正式替代登录方案。

    Returns:
        True 表示登录成功（弹窗已关闭）；False 表示失败。
    """
    logger.info("UI 登录：导航到 su.znzmo.com 触发 LoginModal")
    page.goto(_SU_LOGIN_TRIGGER_URL, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(3000)

    modal = page.locator('[class*="LoginModal__loginModalContainer__"]')
    if not modal.first.is_visible(timeout=5000):
        logger.info("LoginModal 未出现，当前已是登录态")
        return True

    # 手机 tab
    for label in ["手机"]:
        try:
            t = page.locator(f"text={label}").first
            if t.is_visible(timeout=1200):
                t.click()
                page.wait_for_timeout(400)
        except Exception:
            pass

    # 切换账号密码登录
    for label in ["账号密码登录", "密码登录"]:
        try:
            t = page.locator(f"text={label}").first
            if t.is_visible(timeout=1200):
                t.click()
                page.wait_for_timeout(400)
                break
        except Exception:
            pass

    # 填手机号
    for sel in ['input[placeholder*="手机"]', 'input[placeholder*="账号"]', 'input[type="text"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.fill(username)
                break
        except Exception:
            pass

    # 填密码
    for sel in ['input[type="password"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.fill(password)
                break
        except Exception:
            pass

    # 提交
    for sel in ['[class*="login-btn"]', '[class*="loginBtn"]', 'button[type="submit"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1200):
                el.click()
                page.wait_for_timeout(1000)
                break
        except Exception:
            pass

    page.wait_for_timeout(4000)
    closed = not modal.first.is_visible(timeout=2000)
    if closed:
        logger.info("UI 登录成功，.znzmo.com session cookie 已落位")
    else:
        logger.warning("UI 登录后弹窗仍可见，可能凭据有误或网络异常")
    return closed


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
