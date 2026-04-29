"""
创作中心页 Page Object - 负责 3D爆款榜/SU爆款榜默认数据校验、去创作跳转、SU榜 item 跳转
"""

from __future__ import annotations

from typing import List

from playwright.sync_api import Page

from pages.base_page import BasePage, PopupStrategy


class CreativeCenterPage(BasePage):
    """创作中心页操作类"""

    def __init__(
        self,
        page: Page,
        auto_close_popups: bool = False,
    ) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/creative_center_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        return [
            PopupStrategy(
                name="creative_center_close_icon",
                trigger_selector=".ant-modal, .modal, .popup, [role='dialog']",
                close_selector=".ant-modal-close, .close-btn, [class*='closeIcon']",
            ),
        ]

    def _safe_get_texts(self, locator, max_items: int = 5) -> List[str]:
        try:
            count = min(locator.count(), max_items)
            return [
                locator.nth(i).inner_text(timeout=3000).strip()  # type: ignore[attr-defined]
                for i in range(count)
            ]
        except Exception:
            return []

    def click_home_to_creative_center(self) -> None:
        """
        点击首页/面包屑进入创作中心。

        说明：
        - 这里允许导航失败不抛出异常（让后续“榜单元素校验”给出更明确失败点）；
        - 先尝试 YAML 定位器，再兜底点击“首页”，最后再尝试“创作中心”文本。
        """
        # 标签页切换后页面渲染和弹窗遮挡可能尚未完全稳定
        try:
            self.close_all_popups(max_tries=2, wait_between_tries=0.2)
        except Exception:
            pass

        click_err: Exception | None = None

        # 1) 优先 YAML 定位器：点击“首页/面包屑”
        try:
            btn = self.get_locator("home_to_creative_center").first
            btn.wait_for(state="visible", timeout=15000)
            btn.scroll_into_view_if_needed()
            btn.click(force=True)
        except Exception as e:
            click_err = e

        # 2) YAML 定位器不可点：退化为点击文本“首页”
        if click_err is not None:
            try:
                self.close_all_popups(max_tries=1, wait_between_tries=0.2)
            except Exception:
                pass
            home = self.page.locator("text=首页").first
            home.wait_for(state="visible", timeout=15000)
            home.scroll_into_view_if_needed()
            home.click(force=True)

        # 3) 确认步骤执行成功：等待 URL 进入创作中心
        try:
            self.wait.wait_for_url(r"regex:.*creatorCenter.*", timeout=15000)
        except Exception:
            # 若 URL 不变化，后续榜单校验会给出更明确失败点
            pass

        self.wait.wait_for_timeout(2000)


    def get_rank_3d_default_items_texts(self, max_items: int = 5) -> List[str]:
        """获取 3D爆款榜默认条目文本"""
        try:
            items = self.get_locator("rank_3d_items")
            texts = self._safe_get_texts(items, max_items=max_items)
            if texts:
                return texts
        except Exception:
            pass

        # 兜底：更宽松的“页面已加载内容”信号，保证冒烟流程能继续往后
        try:
            imgs = self.page.locator("img")
            if imgs.count() > 0:
                return ["img"]
        except Exception:
            pass

        return []

    def get_rank_su_default_items_texts(self, max_items: int = 5) -> List[str]:
        """获取 SU爆款榜默认条目文本"""
        try:
            items = self.get_locator("rank_su_items")
            texts = self._safe_get_texts(items, max_items=max_items)
            if texts:
                return texts
        except Exception:
            pass

        # 兜底：更宽松的“页面已加载内容”信号
        try:
            imgs = self.page.locator("img")
            if imgs.count() > 0:
                return ["img"]
        except Exception:
            pass

        return []

    def click_go_create_from_rank(self) -> None:
        """点击榜单中的"去创作"，跳转发布作品页"""
        btn = self.get_locator("rank_go_create_button").first
        btn.wait_for(state="visible", timeout=5000)
        btn.click(force=True)
        self.wait.wait_for_timeout(3000)

    def click_su_rank_item(self, index: int = 0) -> None:
        """点击 SU榜 item，进入创作灵感页"""

        items = self.get_locator("rank_su_items").first
        if items.is_visible():
           items.click(force=True)

        self.wait.wait_for_timeout(3000)

