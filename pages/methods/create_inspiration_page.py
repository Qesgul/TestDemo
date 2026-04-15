"""
创作灵感页 Page Object - 负责 SU 模型/二级 Tab/参考模型与灵感展开、搜索页跳转校验
"""

from __future__ import annotations

from typing import List, Optional

from playwright.sync_api import Page

from pages.base_page import BasePage


class CreateInspirationPage(BasePage):
    """创作灵感页操作类"""

    def __init__(
        self,
        page: Optional[Page] = None,
        auto_close_popups: bool = False,
    ) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/create_inspiration_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    def _safe_get_texts(self, locator, max_items: int = 5) -> List[str]:
        """从 Locator 读取文本（失败返回空，便于先跑通流程）"""
        try:
            count = min(locator.count(), max_items)
            return [
                locator.nth(i).inner_text(timeout=3000).strip()  # type: ignore[attr-defined]
                for i in range(count)
            ]
        except Exception:
            return []

    def get_su_model_items_texts(self, max_items: int = 5) -> List[str]:
        """获取 SU 模型列表/默认选中项相关文本"""
        def _try_read() -> List[str]:
            # 1) 读取 YAML 定位器
            try:
                items = self.get_locator("su_model_items")
                if items.count() == 0:
                    # 切页后首次渲染可能稍慢：等到可见再读
                    try:
                        items.first.wait_for(state="visible", timeout=10000)
                    except Exception:
                        pass
                if items.count() > 0:
                    return self._safe_get_texts(items, max_items=max_items)
            except KeyError:
                pass

        return _try_read()

    def switch_any_secondary_tab(self, index: int = 1) -> None:
        """切换任意二级 tab（默认尝试切换到 index=1）"""
        tabs = self.get_locator("su_secondary_tabs")
        if tabs.count() == 0:
            return
        tabs.nth(min(index, tabs.count() - 1)).click(force=True)
        self.wait.wait_for_timeout(2000)


    def click_su_item(self, index: int = 0) -> None:
        """点击 SU 列表 item（用于触发参考模型/灵感展开）"""
        items = self.get_locator("su_model_items")
        if items.count() == 0:
            return
        items.nth(min(index, items.count() - 1)).click(force=True)
        self.wait.wait_for_timeout(2000)


    def get_reference_images_count(self) -> int:
        """获取参考区域图片数量"""
        try:
            imgs = self.get_locator("reference_images")
            return imgs.count()
        except KeyError:
            return 0

    def is_reference_more_button_visible(self) -> bool:
        """“更多”按钮是否可见"""
        try:
            btn = self.get_locator("reference_more_button").first
            return btn.is_visible(timeout=2000)
        except Exception:
            return False

    def click_reference_image_and_get_url(self) -> str:
        """
        点击参考图并返回最终页面 URL。
        使用 BasePage 的标签页管理方法，自动处理新标签页的打开、URL 获取和关闭。

        :return: 跳转后页面的 URL
        """
        original_page = self.page
        # 使用 BasePage 的方法点击并切换到新标签页
        self.switch_to_new_tab(
            self.get_locator("reference_images").first,
            timeout=30000,
            wait_state="domcontentloaded",
            click_kwargs={"force": True}
        )

        # 获取新标签页的 URL
        url = self.page.url

        # 关闭当前标签页（新打开的），并切换回原始页面
        self.close_current_and_switch_to_original(original_page)
        return url

    def click_reference_more_button_and_get_url(self) -> str:
        """
        点击“更多”按钮并返回最终页面 URL。
        使用 BasePage 的标签页管理方法，自动处理新标签页的打开、URL 获取和关闭。

        :return: 跳转后页面的 URL
        """
        original_page = self.page
        # 使用 BasePage 的方法点击并切换到新标签页
        self.switch_to_new_tab(
            self.get_locator("reference_more_button").first,
            timeout=30000,
            wait_state="domcontentloaded",
            click_kwargs={"force": True}
        )
        # 获取新标签页的 URL
        url = self.page.url
        # 关闭当前标签页（新打开的），并切换回原始页面
        self.close_current_and_switch_to_original(original_page)
        return url

    def get_active_tab(self) -> str:
        active_tab = self.get_locator("active_item")
        return active_tab.text_content()

