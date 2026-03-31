"""
首页类 - 提供首页相关操作
"""
from typing import Optional

from playwright.sync_api import Locator
from playwright.sync_api import Page

from core.base_page import BasePage


class HomePage(BasePage):
    """首页类 - 知末网首页"""
    def __init__(
        self,
        page: Optional[Page] = None,
        auto_close_popups: bool = False
    ) -> None:
        """
        HomePage 初始化
        :param page: Playwright Page 对象，可选
        :param auto_close_popups: 初始化时是否自动关闭弹框，默认 False
        """
        super().__init__(page, "pages/elements/home_page_elements.yaml", auto_close_popups)

    @classmethod
    def with_popup_handling(cls, page: Optional[Page] = None) -> "HomePage":
        """工厂方法：创建会自动关闭弹框的 HomePage"""
        return cls(page=page, auto_close_popups=True)

    @classmethod
    def without_popup_handling(cls, page: Optional[Page] = None) -> "HomePage":
        """工厂方法：创建不自动关闭弹框的 HomePage"""
        return cls(page=page, auto_close_popups=False)

    # ===== 页面操作方法 =====
    def goto_homepage(self, url: str = "https://www.znzmo.com/?from=personalCenter") -> None:
        """访问首页，自动关闭弹框"""
        self.goto(url, close_popups_after_load=True, wait_state="networkidle")

    # ===== 页面元素定位方法（从 YAML 读取） =====
    def nav_bar(self) -> Locator:
        return self.get_locator("nav_bar")

    def nav_logo(self) -> Locator:
        return self.get_locator("nav_logo")

    # 筛选框相关
    def filter_container(self) -> Locator:
        return self.get_locator("filter_container")

    def filter_tab_all(self) -> Locator:
        return self.get_locator("filter_tab_all")

    def filter_tab_free(self) -> Locator:
        return self.get_locator("filter_tab_free")

    def filter_tab_vip(self) -> Locator:
        return self.get_locator("filter_tab_vip")

    def filter_type_3dmodel(self) -> Locator:
        return self.get_locator("filter_type_3dmodel")

    def filter_type_texture(self) -> Locator:
        return self.get_locator("filter_type_texture")

    def filter_type_script(self) -> Locator:
        return self.get_locator("filter_type_script")

    # 搜索框
    def search_input(self) -> Locator:
        return self.get_locator("search_input")

    def search_button(self) -> Locator:
        return self.get_locator("search_button")

    # 内容区域
    def content_list(self) -> Locator:
        return self.get_locator("content_list")

    def card_items(self) -> Locator:
        return self.get_locator("card_items")

    # ===== 页面操作方法 =====
    def search(self, keyword: str) -> None:
        """搜索功能"""
        self.search_input().fill(keyword)
        self.search_button().click()

    # ===== 断言方法 =====
    def is_filter_container_visible(self) -> bool:
        """检查筛选框是否可见"""
        try:
            return self.filter_container().is_visible()
        except:
            return False

    def is_all_filter_tabs_visible(self) -> bool:
        """检查所有筛选标签是否可见"""
        try:
            return (
                self.filter_tab_all().is_visible() and
                self.filter_tab_free().is_visible() and
                self.filter_tab_vip().is_visible()
            )
        except:
            return False

    def is_all_filter_types_visible(self) -> bool:
        """检查所有筛选类型是否可见"""
        try:
            return (
                self.filter_type_3dmodel().is_visible() and
                self.filter_type_texture().is_visible() and
                self.filter_type_script().is_visible()
            )
        except:
            return False

    def wait_until_page_ready(self) -> None:
        """等待页面加载完成"""
        self.nav_bar().wait_for(state="visible")
        self.search_input().wait_for(state="visible")
