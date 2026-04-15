"""
基础页面类 - POM基类，支持元素定位、弹框处理、智能等待、多标签页管理
"""
from typing import Any, Callable, List, Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from common.yaml_loader import load_yaml
from core.browser_manager import BrowserManager
from common.wait_utils import WaitUtils


class BasePage:
    """
    页面基础类 - 提供页面操作的通用方法
    支持元素定位、弹框处理、智能等待等功能
    只允许通过定位器进行操作，不支持元素名称映射
    """
    def __init__(
        self,
        page: Optional[Page] = None,
        elements_yaml_path: Optional[str] = None,
        auto_close_popups: bool = False
    ) -> None:
        """
        BasePage 初始化
        :param page: Playwright Page 对象，可选
        :param elements_yaml_path: 页面元素定位文件路径，可选（保留向后兼容）
        :param auto_close_popups: 初始化时是否自动关闭弹框，默认 False
        """
        # 不传 page 时，默认使用共享 page；保证不重复创建 playwright 实例
        self.page = page or BrowserManager.get_default_page()
        self._elements: dict[str, Any] = {}
        if elements_yaml_path:
            self._elements = load_yaml(elements_yaml_path) or {}

        # 智能等待工具
        self.wait = WaitUtils(self.page)

        # 初始化时自动关闭弹框（根据配置）
        if auto_close_popups:
            self.close_all_popups()

    @classmethod
    def with_popup_handling(
        cls,
        page: Optional[Page] = None,
        elements_yaml_path: Optional[str] = None
    ) -> "BasePage":
        """
        工厂方法：创建一个会自动在初始化时关闭弹框的 BasePage 实例
        适用于需要立即清理弹框的场景
        """
        return cls(page=page, elements_yaml_path=elements_yaml_path, auto_close_popups=True)

    @classmethod
    def without_popup_handling(
        cls,
        page: Optional[Page] = None,
        elements_yaml_path: Optional[str] = None
    ) -> "BasePage":
        """
        工厂方法：创建一个不会在初始化时关闭弹框的 BasePage 实例
        适用于需要查看弹框内容的测试场景
        """
        return cls(page=page, elements_yaml_path=elements_yaml_path, auto_close_popups=False)

    # ===== 弹框处理通用方法 =====
    def close_all_popups(self, max_tries: int = 3, wait_between_tries: float = 0.5) -> int:
        """
        关闭所有可能出现的弹窗
        :param max_tries: 最大尝试次数
        :param wait_between_tries: 每次尝试之间等待时间(秒)
        :return: 关闭的弹窗数量
        """
        close_selectors = [
            ".ant-modal-close",
            "button[class*='close']",
            "button.ant-modal-close",
            ".close-btn",
            "[aria-label='Close']",
            ".modal-close",
            "text=关闭",
            "text=×"
        ]

        closed_count = 0
        for _ in range(max_tries):
            found_popup = False
            for sel in close_selectors:
                try:
                    close_btn = self.page.locator(sel).first
                    if close_btn.is_visible(timeout=1000):
                        try:
                            close_btn.click(force=True)
                            closed_count += 1
                            found_popup = True
                            self.wait.wait_for_timeout(int(wait_between_tries * 1000))
                        except:
                            continue
                except:
                    continue
            if not found_popup:
                break
        return closed_count

    def close_popup_by_selector(self, selector: str, timeout: float = 2.0) -> bool:
        """
        关闭指定选择器的弹框
        :param selector: 弹框关闭按钮选择器
        :param timeout: 超时时间(秒)
        :return: 是否成功关闭
        """
        try:
            close_btn = self.page.locator(selector).first
            if close_btn.is_visible(timeout=int(timeout * 1000)):
                close_btn.click(force=True)
                return True
        except:
            pass
        return False

    def goto(self, url: str, close_popups_after_load: bool = True, wait_state: str = "networkidle") -> None:
        """
        访问页面，加载完成后自动关闭弹框
        :param url: 页面URL
        :param close_popups_after_load: 是否在页面加载后关闭弹框
        :param wait_state: 等待状态 (domcontentloaded, load, networkidle)
        """
        # Playwright 默认等待 "load" 在某些页面可能持续资源加载而卡住；
        # 这里先按 "domcontentloaded" 返回，随后由 WaitUtils 再按 wait_state 做最终等待。
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.wait.wait_for_page_load(wait_state)
        except PlaywrightTimeoutError:
            # 对于部分站点可能持续发起请求，导致 networkidle 不稳定；
            # 这里做降级等待，避免整个用例因页面“永远不 idle”失败。
            if wait_state == "networkidle":
                self.wait.wait_for_page_load("domcontentloaded", timeout=10.0)
            else:
                raise
        if close_popups_after_load:
            self.close_all_popups()

    def locator(self, selector: str) -> Locator:
        """获取 Playwright Locator 对象"""
        return self.page.locator(selector)

    def get_locator(self, name: str) -> Locator:
        """
        从 YAML 配置中获取元素定位器
        :param name: YAML 中定义的元素名称
        :return: Playwright Locator 对象
        """
        if name not in self._elements:
            raise KeyError(f"未在页面元素yaml中找到元素: {name}")
        return self.page.locator(str(self._elements[name]))

    # ===== 元素操作方法 =====
    def wait_for_element(self, selector: str, state: str = "visible") -> Locator:
        """
        等待元素进入指定状态
        :param selector: CSS选择器
        :param state: 等待状态 (visible/hidden)
        :return: Locator 对象
        """
        element = self.locator(selector)
        element.wait_for(state=state)
        return element

    def fill(self, selector: str, value: str) -> None:
        """填充输入框"""
        self.wait_for_element(selector).fill(value)

    def click(self, selector: str) -> None:
        """点击元素"""
        self.wait_for_element(selector).click()

    def click_if_visible(self, selector: str) -> bool:
        """如果可见就点击"""
        if not self.locator(selector).is_visible():
            return False
        self.locator(selector).click()
        return True

    def text_of(self, selector: str) -> str:
        """获取元素文本"""
        return self.wait_for_element(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        """检查元素是否可见"""
        return self.locator(selector).is_visible()

    # ===== 多标签页管理方法 =====

    def switch_to_page(self, target_page: Page) -> None:
        """
        切换 self.page 到指定的 Page 对象，同步更新 self.wait。
        :param target_page: 要切换到的 Playwright Page 对象
        """
        self.page = target_page
        self.wait = WaitUtils(self.page)

    def click_and_switch_to_new_tab(
        self,
        click_action: Callable[[], Any],
        timeout: int = 30000,
        wait_state: str = "domcontentloaded",
    ) -> Page:
        """
        执行点击操作并等待新标签页打开，自动切换 self.page 到新标签页。

        :param click_action: 可调用对象，执行实际的点击（如 lambda: locator.click()）
        :param timeout: 等待新标签页的超时时间（毫秒）
        :param wait_state: 新标签页加载等待状态
        :return: 新标签页的 Page 对象（self.page 已更新）
        """
        context = self.page.context
        with context.expect_page(timeout=timeout) as new_page_info:
            click_action()
        new_page: Page = new_page_info.value
        new_page.wait_for_load_state(wait_state, timeout=timeout)
        self.switch_to_page(new_page)
        return new_page

    def click_locator_and_switch_to_new_tab(
        self,
        locator: Locator,
        timeout: int = 30000,
        wait_state: str = "domcontentloaded",
        click_kwargs: Optional[dict] = None,
    ) -> Page:
        """
        点击指定的 Locator 并等待新标签页打开，自动切换 self.page 到新标签页。

        :param locator: 要点击的 Playwright Locator 对象
        :param timeout: 等待新标签页的超时时间（毫秒）
        :param wait_state: 新标签页加载等待状态
        :param click_kwargs: 传递给 click() 的额外参数字典
        :return: 新标签页的 Page 对象（self.page 已更新）
        """
        click_kwargs = click_kwargs or {}

        def do_click():
            locator.click(**click_kwargs)

        return self.click_and_switch_to_new_tab(do_click, timeout, wait_state)

    def click_element_by_selector_and_switch_to_new_tab(
        self,
        selector: str,
        timeout: int = 30000,
        wait_state: str = "domcontentloaded",
        click_kwargs: Optional[dict] = None,
    ) -> Page:
        """
        通过 CSS 选择器定位元素并点击，等待新标签页打开，自动切换 self.page。

        :param selector: CSS 选择器
        :param timeout: 等待新标签页的超时时间（毫秒）
        :param wait_state: 新标签页加载等待状态
        :param click_kwargs: 传递给 click() 的额外参数字典
        :return: 新标签页的 Page 对象（self.page 已更新）
        """
        locator = self.locator(selector)
        return self.click_locator_and_switch_to_new_tab(
            locator, timeout, wait_state, click_kwargs
        )

    def click_element_by_name_and_switch_to_new_tab(
        self,
        element_name: str,
        timeout: int = 30000,
        wait_state: str = "domcontentloaded",
        click_kwargs: Optional[dict] = None,
    ) -> Page:
        """
        通过 YAML 中定义的元素名称定位并点击，等待新标签页打开，自动切换 self.page。

        :param element_name: YAML 中定义的元素名称
        :param timeout: 等待新标签页的超时时间（毫秒）
        :param wait_state: 新标签页加载等待状态
        :param click_kwargs: 传递给 click() 的额外参数字典
        :return: 新标签页的 Page 对象（self.page 已更新）
        """
        locator = self.get_locator(element_name)
        return self.click_locator_and_switch_to_new_tab(
            locator, timeout, wait_state, click_kwargs
        )

    def close_current_and_switch_back(self) -> Page:
        """
        关闭当前标签页，切换回 context 中最后一个存活的标签页。
        :return: 切换后的 Page 对象（self.page 已更新）
        """
        context = self.page.context
        if not self.page.is_closed():
            self.page.close()

        alive_pages: List[Page] = [p for p in context.pages if not p.is_closed()]
        if not alive_pages:
            raise RuntimeError("所有标签页均已关闭，无法切换")
        self.switch_to_page(alive_pages[-1])
        return self.page

    def close_current_and_switch_to_original(self, original_page: Page) -> Page:
        """
        关闭当前标签页，切换回指定的原始标签页。

        :param original_page: 要切换回的原始 Page 对象
        :return: 切换后的 Page 对象（self.page 已更新）
        """
        if self.page is not original_page and not self.page.is_closed():
            self.page.close()

        if original_page.is_closed():
            raise RuntimeError("原始标签页已关闭，无法切换")

        self.switch_to_page(original_page)
        return self.page

    def close_other_tabs(self) -> int:
        """
        关闭除当前 self.page 之外的所有标签页。
        :return: 关闭的标签页数量
        """
        context = self.page.context
        closed = 0
        for p in context.pages:
            if p is not self.page and not p.is_closed():
                try:
                    p.close()
                    closed += 1
                except Exception:
                    pass
        return closed

    def get_all_alive_pages(self) -> List[Page]:
        """
        获取所有存活的标签页列表。
        :return: 存活的 Page 对象列表
        """
        context = self.page.context
        return [p for p in context.pages if not p.is_closed()]

    def get_current_url(self):
        # 强制获取浏览器真实URL
        return self.page.evaluate("window.location.href")
