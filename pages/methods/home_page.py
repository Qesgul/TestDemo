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
            # 支付/套餐弹窗：外层容器为 ant-modal-wrap，尝试标准 ant-modal-close
            PopupStrategy(
                name="homepage_payment_modal_std_close",
                trigger_selector=".ant-modal-wrap",
                close_selector=".ant-modal-close",
            ),
            # 支付弹窗变体：closeIcon CSS 模块类名
            PopupStrategy(
                name="homepage_payment_modal_icon_close",
                trigger_selector=".ant-modal-wrap",
                close_selector="[class*='closeIcon'], [class*='close-icon'], [class*='CloseIcon']",
            ),
        ]

    # ===== 页面操作方法 =====
    def goto_homepage(self, url: str = "https://www.znzmo.com/?from=personalCenter") -> None:
        """访问首页。默认 reload 一次以关弹窗（保留 base goto 默认行为）。"""
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
        except Exception:
            return False

    def is_all_filter_tabs_visible(self) -> bool:
        """检查所有筛选标签是否可见"""
        try:
            return (
                self.filter_tab_all().is_visible() and
                self.filter_tab_free().is_visible() and
                self.filter_tab_vip().is_visible()
            )
        except Exception:
            return False

    def is_all_filter_types_visible(self) -> bool:
        """检查所有筛选类型是否可见"""
        try:
            return (
                self.filter_type_3dmodel().is_visible() and
                self.filter_type_texture().is_visible() and
                self.filter_type_script().is_visible()
            )
        except Exception:
            return False

    def wait_until_page_ready(self) -> None:
        """等待页面加载完成"""
        self.nav_bar().wait_for(state="visible")
        self.search_input().wait_for(state="visible")

    # ===== 弹框关闭辅助 =====
    def _dismiss_blocking_modal(self) -> None:
        """关闭可能遮挡操作的模态弹框。

        策略：若检测到 ant-modal-wrap，直接刷新页面（最可靠方式）。
        刷新后弹框消失，页面恢复到已登录首页状态，再继续后续导航操作。
        """
        try:
            if self.page.locator(".ant-modal-wrap").is_visible(timeout=500):
                self.page.reload(wait_until="domcontentloaded")
                self.wait.wait_for_timeout(1000)
        except Exception:
            pass

    # ===== 创作灵感冒烟用例需要的方法 =====
    def goto_create_inspiration_from_nav(self) -> None:
        """悬停上传菜单，点击创作灵感。

        hover 前先关闭可能遮挡的弹框（支付弹窗在 networkidle 后延迟弹出）；
        定位器优先从 home_page_elements.yaml 读取；
        若定位器尚未补齐（KeyError），退化为文本定位兜底写法。
        """
        self._dismiss_blocking_modal()

        try:
            upload = self.get_locator("nav_create_upload")
            inspiration = self.get_locator("nav_create_inspiration")
            upload.first.hover(force=True)
            inspiration.first.click(force=True)

        except KeyError:
            # 兜底：文本匹配
            self.page.locator("text=创作上传").first.hover(force=True)
            self.page.locator("text=创作灵感").first.click(force=True)

        # 等待二级菜单/页面跳转稳定
        self.wait.wait_for_timeout(2000)

    def goto_create_inspiration_from_nav_and_switch(self) -> Page:
        """悬停上传菜单，点击创作灵感，并切换到新标签页（如打开了新标签页）。

        hover 前先关闭可能遮挡的弹框（支付弹窗等在 networkidle 后延迟弹出）；
        使用短超时（3s）检测是否打开新标签页：
          - 若打开新标签页 → 切换到新标签页；
          - 若未打开新标签页 → 当前页已在同一 tab 内导航，等待稳定后返回。
        不再调用 goto_create_inspiration_from_nav() 作为 fallback，
        避免在已导航页面上重复操作导致状态混乱。

        Returns:
            切换（或保持）后的当前 Page。
        """
        self._dismiss_blocking_modal()
        context = self.page.context

        # 1) 悬停展开下拉菜单
        try:
            upload = self.get_locator("nav_create_upload")
            upload.first.hover(force=True)
        except (KeyError, Exception):
            try:
                self.page.locator("text=创作上传").first.hover(force=True)
            except Exception:
                pass
        self.wait.wait_for_timeout(500)  # 等待下拉菜单展开

        # 2) 点击"创作灵感"，用短超时检测是否打开新标签页
        try:
            try:
                inspiration = self.get_locator("nav_create_inspiration")
            except KeyError:
                inspiration = self.page.locator("text=创作灵感")

            try:
                # 短超时：3s 内若无新标签页，说明是同 tab 内导航
                with context.expect_page(timeout=3000) as new_page_info:
                    inspiration.first.click(force=True)
                # 新标签页打开 → 切换过去（即使 load_state 超时也要切换）
                new_page = new_page_info.value
                try:
                    new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                self.switch_to_page(new_page)
            except Exception:
                # 未检测到新标签页（同 tab 内导航或点击失败），等待页面稳定
                self.wait.wait_for_timeout(2000)
        except Exception:
            pass

        return self.page

    def close_current_tab_and_switch_back(self) -> "HomePage":
        """关闭当前标签页，切换回上一个标签页。

        Returns:
            self（支持链式调用）
        """
        self.close_current_and_switch_back()
        return self

    def close_other_tabs(self) -> "HomePage":
        """关闭除当前标签页之外的所有标签页。

        Returns:
            self（支持链式调用）
        """
        self._last_closed_tab_count = super().close_other_tabs()
        return self

    def get_last_closed_tab_count(self) -> int:
        """获取最后一次调用 close_other_tabs 关闭的标签页数量。

        Returns:
            关闭的标签页数量
        """
        return getattr(self, "_last_closed_tab_count", 0)
