"""
基础页面类 - POM基类，支持元素定位、弹框处理、智能等待
"""
from typing import Any, Optional

from playwright.sync_api import Locator, Page

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
        self.page.goto(url)
        self.wait.wait_for_page_load(wait_state)
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
