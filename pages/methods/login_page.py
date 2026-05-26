"""
登录页面类 - 提供登录功能操作

支持两种登录方式：
1. Cookie 优先登录（默认）：先尝试 cookie 恢复会话，失效时自动回退到密码登录
2. 纯密码登录：跳过 cookie，直接走账号密码流程

性能要点：
- 多个候选选择器用 ``Locator.or_(...).first`` 合并到一次 wait，避免串行 is_visible 累积；
- 单点 timeout 缩到 800-1500ms，快速失败优于慢慢轮询；
- cookie 注入后直接校验登录态，不再 ``page.reload(networkidle)``；
- 提交后用 ``wait_for_url`` 而非 ``wait_for_load_state(networkidle)``。
"""
import logging
import re
from typing import List

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pages.base_page import PopupStrategy
from pages.base_page import BasePage
from common.cookie_manager import CookieManager

_logger = logging.getLogger(__name__)

_LOGIN_STATE_CHECK_TIMEOUT = 1500
_FAST_CLICK_TIMEOUT = 1500
_POST_LOGIN_URL_PATTERN = re.compile(r"personalCenter|index|home|/$|\.html")


class LoginPage(BasePage):
    """登录页面类 - 知末网登录功能"""
    def __init__(
        self,
        page: Page,
        auto_close_popups: bool = False
    ) -> None:
        super().__init__(page, "pages/elements/login_page_elements.yaml", auto_close_popups)

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        return [
            PopupStrategy(
                name="login_specific_close_icon",
                trigger_selector=".ant-modal, .modal, .popup, [role='dialog']",
                close_selector='[class*="closeIcon"], [class*="close-icon"]',
            ),
        ]

    # ===== 页面导航 =====
    def goto_login_page(self, url: str = "https://www.znzmo.com/?from=personalCenter") -> None:
        """访问登录页面，默认 reload 一次关弹窗（与 base goto 默认一致）。"""
        self.goto(url, close_popups_after_load=True)

    # ===== 登录状态判断 =====
    def _is_logged_in(self) -> bool:
        """
        检测当前页面是否处于已登录状态。

        判断依据：未登录时 login_register_button（notLoginBox）可见；
        已登录时该元素不存在或不可见。
        """
        try:
            btn = self.get_locator("login_register_button").first
            return not btn.is_visible(timeout=_LOGIN_STATE_CHECK_TIMEOUT)
        except (KeyError, PlaywrightTimeoutError, PlaywrightError):
            return False

    # ===== Cookie 登录 =====
    def _try_cookie_login(self, username: str) -> bool:
        """
        尝试用本地 cookie 恢复登录会话。

        改进点：
        - 调用 is_cookie_valid 时传入 username，校验 cookie 文件内账号与请求账号一致
        - cookie 不可用时主动清理 context 残留 cookie，防止切换账号时串号
        - 注入 cookie 后不再 page.reload(networkidle)，直接校验登录态

        :return: True 表示 cookie 登录成功且验证通过
        """
        cookie_data = CookieManager.load_cookies(username)
        if not cookie_data or not CookieManager.is_cookie_valid(
            cookie_data, expected_account_identifier=username
        ):
            _logger.info("账号 %s 未找到匹配的有效 cookie，跳过 cookie 登录", username)
            # 主动清理 context 残留 cookie，防止切换账号时复用旧登录态
            try:
                self.page.context.clear_cookies()
            except Exception:
                pass
            return False

        _logger.info("账号 %s 检测到有效 cookie，尝试恢复会话", username)
        context = self.page.context
        try:
            context.clear_cookies()
            CookieManager.set_cookies_to_context(context, cookie_data)
            # 短等让客户端 JS 感知新 cookie，避免立即检查时仍是旧态
            self.page.wait_for_timeout(200)

            if self._is_logged_in():
                _logger.info("账号 %s cookie 登录验证通过", username)
                return True

            _logger.warning("账号 %s cookie 已注入但登录状态验证失败，cookie 可能已失效", username)
            CookieManager.delete_cookies(username)
            return False
        except Exception as e:
            _logger.warning("cookie 登录过程异常: %s", e)
            return False

    # ===== 密码登录（内部实现） =====
    def _login_with_credentials(self, username: str, password: str) -> None:
        """账号密码登录的完整流程（不涉及 cookie）。

        优化：
        - 多候选选择器用 ``Locator.or_().first`` 合并，避免串行 is_visible(2000ms) 累计；
        - 提交后用 ``wait_for_url`` 替代 ``wait_for_load_state(networkidle)``。
        """
        _logger.info("开始账号密码登录流程")

        phone_login_opt = self.get_locator("phone_login_option").first

        # ---- 1. 点击「登录/注册」入口（仅当 phone_login_option 不可见时）----
        if not phone_login_opt.is_visible(timeout=300):
            _logger.info("点击登录/注册入口")
            try:
                login_entry = (
                    self.get_locator("login_register_button").first
                    .or_(self.page.locator("div").filter(has_text="登录/注册").first)
                )
                login_entry.click(force=True, timeout=_FAST_CLICK_TIMEOUT)
            except (KeyError, PlaywrightTimeoutError, PlaywrightError):
                pass
            try:
                phone_login_opt.wait_for(state="visible", timeout=3000)
            except PlaywrightTimeoutError:
                pass

        # ---- 2. 切换到手机登录（如果当前不是）----
        try:
            if phone_login_opt.is_visible(timeout=300):
                phone_login_opt.click(force=True, timeout=_FAST_CLICK_TIMEOUT)
        except (KeyError, PlaywrightTimeoutError, PlaywrightError):
            pass

        # ---- 3. 切换到账号密码登录（or_ 合并多文案候选）----
        _logger.info("切换到账号密码登录")
        try:
            pwd_login_tab = (
                self.page.locator("text=账号密码登录")
                .or_(self.page.locator("text=密码登录"))
                .first
            )
            pwd_login_tab.click(force=True, timeout=_FAST_CLICK_TIMEOUT)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass  # 已在密码登录页或 UI 变化，跳过

        # ---- 4. 等账号输入框可见后填写 ----
        try:
            username_el = self.get_locator("username_input").first
            username_el.wait_for(state="visible", timeout=3000)
            username_el.fill(username)
            self.get_locator("password_input").first.fill(password)
        except (KeyError, PlaywrightTimeoutError, PlaywrightError) as e:
            _logger.warning("账号密码填写异常: %s", e)

        # ---- 5. 提交并等待跳转（wait_for_url 优于 networkidle）----
        _logger.info("点击登录提交")
        self.get_locator("submit_button").click()
        try:
            self.page.wait_for_url(_POST_LOGIN_URL_PATTERN, timeout=8000)
        except PlaywrightTimeoutError:
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except PlaywrightTimeoutError:
                pass

    # ===== 公开登录方法 =====
    def login_with(self, username: str, password: str, *, use_cookie: bool = True) -> None:
        """
        默认登录入口 —— 优先尝试 cookie 登录，失败后自动回退到密码登录。

        :param username: 用户名（手机号）
        :param password: 密码
        :param use_cookie: 是否启用 cookie 优先策略，默认 True
        """
        _logger.info("开始知末网登录流程 (cookie 优先=%s)", use_cookie)

        if use_cookie and self._try_cookie_login(username):
            return

        self._login_with_credentials(username, password)

        try:
            CookieManager.save_cookies(username, self.page.context)
            _logger.info("登录成功，cookie 已保存")
        except Exception as e:
            _logger.warning("cookie 保存失败（不影响本次登录）: %s", e)

    def login_with_password(self, username: str, password: str) -> None:
        """
        强制使用账号密码登录，跳过 cookie 策略。

        适用于需要确保走完整密码登录流程的场景（如测试登录 UI）。
        """
        _logger.info("强制密码登录（跳过 cookie）")
        self._login_with_credentials(username, password)

    def wait_until_ready(self) -> None:
        """
        等待登录页面关键元素可交互。

        Playwright 的 action 方法（fill / click）内置 auto-wait，
        多数场景无需显式调用。仅在需要「先断言页面就绪」时使用。
        """
        self.get_locator("username_input").wait_for(state="visible")
        self.get_locator("password_input").wait_for(state="visible")
        self.get_locator("submit_button").wait_for(state="visible")
