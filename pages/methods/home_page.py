"""
首页类 - 提供首页相关操作
"""
from typing import List

from playwright.sync_api import Locator
from playwright.sync_api import Page

from pages.base_page import PopupStrategy
from pages.base_page import BasePage


class HomePage(BasePage):
    """首页类 - 知末网首页"""
    def __init__(
        self,
        page: Page,
        auto_close_popups: bool = False
    ) -> None:
        """
        HomePage 初始化
        :param page: Playwright Page 对象，可选
        :param auto_close_popups: 初始化时是否自动关闭弹框，默认 False
        """
        super().__init__(page, "pages/elements/home_page_elements.yaml", auto_close_popups)

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        return [
            PopupStrategy(
                name="homepage_generic_dialog_close",
                trigger_selector=".ant-modal, .modal, .popup, [role='dialog']",
                close_selector=".ant-modal-close, .close-btn, [class*='closeIcon']",
            ),
        ]

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

    # ===== 创作灵感冒烟用例需要的方法（可按实际页面微调定位器）=====
    def goto_create_inspiration_from_nav(self) -> None:
        """
        悬停导航“创作上传”，点击“创作灵感”。

        说明：
        - 定位器优先从 `pages/elements/home_page_elements.yaml` 读取；
        - 若定位器尚未补齐（KeyError），则退化为使用文本定位的兜底写法，便于先跑通流程。
        """
        try:
            upload = self.get_locator("nav_create_upload")
            inspiration = self.get_locator("nav_create_inspiration")
            upload.first.hover()
            inspiration.first.click()

        except KeyError:
            # 兜底：用文本匹配尽量靠近真实页面结构
            self.page.locator("text=创作上传").first.hover()
            self.page.locator("text=创作灵感").first.click()

        # 等待二级菜单/页面跳转稳定
        self.wait.wait_for_timeout(2000)

    def goto_create_inspiration_from_nav_and_switch(self) -> Page:
        """
        悬停导航“创作上传”，点击“创作灵感”，并切换到新标签页（如果打开了新标签页）。

        说明：
        - 如果点击后打开了新标签页，则自动切换到新标签页；
        - 否则继续在当前页操作。
        
        :return: 切换（或保持）后的当前 `Page`
        """
        try:
            upload = self.get_locator("nav_create_upload")
            inspiration = self.get_locator("nav_create_inspiration")
            upload.first.hover()

            # 尝试点击并等待新标签页
            self.switch_to_new_tab(inspiration.first)
            return self.page

        except Exception:
            # 如果没有打开新标签页，回退到普通点击
            self.goto_create_inspiration_from_nav()
            return self.page

    def close_current_tab_and_switch_back(self) -> "HomePage":
        """
        关闭当前标签页，切换回上一个标签页。

        :return: 返回 self（支持链式调用）
        """
        self.close_current_and_switch_back()
        return self

    def close_other_tabs(self) -> "HomePage":
        """
        关闭除当前标签页之外的所有标签页。

        :return: 返回 self（支持链式调用）
        """
        self._last_closed_tab_count = super().close_other_tabs()
        return self

    def get_last_closed_tab_count(self) -> int:
        """
        获取最后一次调用 close_other_tabs 关闭的标签页数量。

        :return: 关闭的标签页数量
        """
        return getattr(self, '_last_closed_tab_count', 0)
