"""
智能等待工具类 - 基于 Playwright 的高级等待机制
支持元素可点击、页面加载完成、网络请求完成等多维度等待
"""
import re
from typing import Optional, List, Union
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class WaitUtils:
    """智能等待工具类"""

    def __init__(self, page: Page):
        """
        初始化等待工具
        :param page: Playwright Page 对象
        """
        self.page = page

    def wait_for_element_visible(self, selector: str, timeout: float = 30.0) -> Locator:
        """
        等待元素可见
        :param selector: CSS选择器
        :param timeout: 超时时间（秒）
        :return: Locator对象
        """
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=int(timeout * 1000))
        return locator

    def wait_for_element_hidden(self, selector: str, timeout: float = 30.0) -> None:
        """
        等待元素隐藏
        :param selector: CSS选择器
        :param timeout: 超时时间（秒）
        """
        locator = self.page.locator(selector)
        locator.wait_for(state="hidden", timeout=int(timeout * 1000))

    def wait_for_element_clickable(self, selector: str, timeout: float = 30.0) -> Locator:
        """
        等待元素可点击（可见且启用）
        :param selector: CSS选择器
        :param timeout: 超时时间（秒）
        :return: Locator对象
        """
        locator = self.wait_for_element_visible(selector, timeout)
        # 等待元素启用
        locator.wait_for(state="visible", timeout=int(timeout * 1000))
        # 检查元素是否被禁用
        if locator.is_disabled():
            raise PlaywrightTimeoutError(f"元素 {selector} 已可见但不可点击（被禁用）")
        return locator

    def wait_for_page_load(self, wait_state: str = "networkidle", timeout: float = 60.0) -> None:
        """
        等待页面加载完成
        :param wait_state: 等待状态 (domcontentloaded, load, networkidle)
        :param timeout: 超时时间（秒）
        """
        valid_states = ["domcontentloaded", "load", "networkidle"]
        if wait_state not in valid_states:
            raise ValueError(f"无效的等待状态: {wait_state}，必须是 {valid_states}")

        self.page.wait_for_load_state(wait_state, timeout=int(timeout * 1000))

    def wait_for_url(self, url_pattern: Union[str, re.Pattern], timeout: float = 30.0) -> str:
        """
        等待URL匹配模式
        :param url_pattern: URL字符串或正则表达式
        :param timeout: 超时时间（秒）
        :return: 匹配到的URL
        """
        if isinstance(url_pattern, str):
            # 如果是字符串，检查是否完全匹配或包含
            if url_pattern.startswith("regex:"):
                pattern = re.compile(url_pattern[6:])
            elif "*" in url_pattern or "?" in url_pattern:
                # 简单的通配符转换为正则表达式
                pattern = re.compile(re.escape(url_pattern).replace("\\*", ".*").replace("\\?", "."))
            else:
                # 精确匹配
                pattern = re.compile(re.escape(url_pattern))
        else:
            pattern = url_pattern

        def check_url():
            current_url = self.page.url
            if pattern.search(current_url):
                return current_url
            return None

        try:
            self.page.wait_for_function(
                lambda: check_url() is not None,
                timeout=int(timeout * 1000)
            )
            return self.page.url
        except PlaywrightTimeoutError:
            raise PlaywrightTimeoutError(
                f"URL匹配超时。当前URL: {self.page.url}, "
                f"期望模式: {url_pattern}"
            )

    def wait_for_network_idle(self, timeout: float = 30.0) -> None:
        """
        等待网络请求完成（所有请求结束）
        :param timeout: 超时时间（秒）
        """
        self.page.wait_for_load_state("networkidle", timeout=int(timeout * 1000))

    def wait_for_request_finished(self, url_pattern: Union[str, re.Pattern], timeout: float = 30.0) -> None:
        """
        等待特定网络请求完成
        :param url_pattern: 请求URL模式（字符串或正则表达式）
        :param timeout: 超时时间（秒）
        """
        request_finished = False

        def on_request_finished(request):
            nonlocal request_finished
            if isinstance(url_pattern, str):
                if url_pattern in request.url:
                    request_finished = True
            else:
                if url_pattern.search(request.url):
                    request_finished = True

        # 监听请求完成事件
        listener = self.page.on("requestfinished", on_request_finished)

        try:
            self.page.wait_for_function(
                lambda: request_finished,
                timeout=int(timeout * 1000)
            )
        finally:
            # 移除监听器
            self.page.remove_listener("requestfinished", listener)

    def wait_for_response(self, url_pattern: Union[str, re.Pattern], timeout: float = 30.0) -> None:
        """
        等待特定响应
        :param url_pattern: 响应URL模式（字符串或正则表达式）
        :param timeout: 超时时间（秒）
        """
        self.page.wait_for_response(
            lambda response: (
                (isinstance(url_pattern, str) and url_pattern in response.url) or
                (isinstance(url_pattern, re.Pattern) and url_pattern.search(response.url))
            ),
            timeout=int(timeout * 1000)
        )

    def wait_for_selector_count(self, selector: str, count: int, timeout: float = 30.0) -> List[Locator]:
        """
        等待选择器匹配的元素数量达到指定值
        :param selector: CSS选择器
        :param count: 期望的元素数量
        :param timeout: 超时时间（秒）
        :return: 匹配到的元素列表
        """
        def check_count():
            elements = self.page.locator(selector)
            return elements.count() == count

        self.page.wait_for_function(
            lambda: check_count(),
            timeout=int(timeout * 1000)
        )
        return list(self.page.locator(selector).all())

    def wait_for_text(self, selector: str, text_pattern: Union[str, re.Pattern], timeout: float = 30.0) -> str:
        """
        等待元素包含指定文本
        :param selector: CSS选择器
        :param text_pattern: 文本模式（字符串或正则表达式）
        :param timeout: 超时时间（秒）
        :return: 匹配到的文本
        """
        locator = self.wait_for_element_visible(selector, timeout)

        def check_text():
            text = locator.inner_text()
            if isinstance(text_pattern, str):
                return text_pattern in text
            else:
                return text_pattern.search(text) is not None

        self.page.wait_for_function(
            lambda: check_text(),
            timeout=int(timeout * 1000)
        )
        return locator.inner_text()

    def wait_for_attribute(self, selector: str, attribute: str, value_pattern: Union[str, re.Pattern],
                          timeout: float = 30.0) -> str:
        """
        等待元素属性匹配指定值
        :param selector: CSS选择器
        :param attribute: 属性名称
        :param value_pattern: 属性值模式（字符串或正则表达式）
        :param timeout: 超时时间（秒）
        :return: 匹配到的属性值
        """
        locator = self.wait_for_element_visible(selector, timeout)

        def check_attribute():
            value = locator.get_attribute(attribute) or ""
            if isinstance(value_pattern, str):
                return value_pattern in value
            else:
                return value_pattern.search(value) is not None

        self.page.wait_for_function(
            lambda: check_attribute(),
            timeout=int(timeout * 1000)
        )
        return locator.get_attribute(attribute) or ""

    def safe_click(self, selector: str, timeout: float = 30.0, retries: int = 2) -> None:
        """
        安全点击方法 - 处理可能的点击失败
        :param selector: CSS选择器
        :param timeout: 超时时间（秒）
        :param retries: 重试次数
        """
        for attempt in range(retries + 1):
            try:
                element = self.wait_for_element_clickable(selector, timeout)
                element.click(timeout=int(timeout * 1000))
                return
            except Exception as e:
                if attempt == retries:
                    raise
                # 等待一段时间后重试
                self.page.wait_for_timeout(500)
                # 可能需要滚动到元素可见位置
                self.page.evaluate(f"document.querySelector('{selector}')?.scrollIntoView()")

    @staticmethod
    def wait_for_timeout(milliseconds: float) -> None:
        """
        显式等待（替代time.sleep）
        :param milliseconds: 等待时间（毫秒）
        """
        # 注意：尽量避免使用这种方式，优先使用其他等待方法
        import time
        time.sleep(milliseconds / 1000)
