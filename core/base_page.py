from typing import Any, Optional
import time

from playwright.sync_api import Locator, Page

from common.yaml_loader import load_yaml
from core.browser_manager import BrowserManager


class BasePage:
    def __init__(
        self,
        page: Optional[Page] = None,
        elements_yaml_path: Optional[str] = None,
        auto_close_popups: bool = False
    ) -> None:
        """
        BasePage 初始化
        :param page: Playwright Page 对象，可选
        :param elements_yaml_path: 页面元素定位文件路径，可选
        :param auto_close_popups: 初始化时是否自动关闭弹框，默认 False（不自动关闭）
        """
        # 不传 page 时，默认使用共享 page；保证不重复创建 playwright 实例
        self.page = page or BrowserManager.get_default_page()
        self._elements: dict[str, Any] = {}
        if elements_yaml_path:
            self._elements = load_yaml(elements_yaml_path) or {}

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
                            time.sleep(wait_between_tries)
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
        self.page.wait_for_load_state(wait_state)
        if close_popups_after_load:
            self.close_all_popups()

    def locator(self, locator: str) -> Locator:
        return self.page.locator(locator)

    def element_selector(self, name: str) -> str:
        if name not in self._elements:
            raise KeyError(f"未在页面元素yaml中找到元素: {name}")
        return str(self._elements[name])

    def element(self, name: str) -> Locator:
        return self.locator(self.element_selector(name))

    def wait_element_visible(self, name: str) -> Locator:
        target = self.element(name)
        target.wait_for(state="visible")
        return target

    def wait_visible(self, locator: str) -> Locator:
        target = self.locator(locator)
        target.wait_for(state="visible")
        return target

    def is_visible(self, locator: str) -> bool:
        return self.locator(locator).is_visible()

    def fill(self, locator: str, value: str) -> None:
        self.wait_visible(locator).fill(value)

    def fill_element(self, name: str, value: str) -> None:
        self.wait_element_visible(name).fill(value)

    def click(self, locator: str) -> None:
        self.wait_visible(locator).click()

    def click_element(self, name: str) -> None:
        self.wait_element_visible(name).click()

    def click_if_visible(self, locator: str) -> bool:
        if not self.is_visible(locator):
            return False
        self.locator(locator).click()
        return True

    def click_element_if_visible(self, name: str) -> bool:
        target = self.element(name)
        if not target.is_visible():
            return False
        target.click()
        return True

    def text_of(self, locator: str) -> str:
        return self.wait_visible(locator).inner_text()

    def text_of_element(self, name: str) -> str:
        return self.wait_element_visible(name).inner_text()
