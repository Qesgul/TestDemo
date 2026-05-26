"""
创作灵感页 Page Object - 负责 SU 模型/二级 Tab/参考模型与灵感展开、搜索页跳转校验
"""

from __future__ import annotations

from typing import List

from playwright.sync_api import Page

from pages.base_page import BasePage


class CreateInspirationPage(BasePage):
    """创作灵感页操作类"""

    def __init__(
        self,
        page: Page,
        auto_close_popups: bool = False,
    ) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/create_inspiration_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    # 不参与存储/比对的按钮/固定标签文本（完整匹配）
    _SKIP_TEXTS: set[str] = {"去创作", "近30天预估收益"}

    def _safe_get_texts(self, locator, max_items: int = 0) -> List[str]:
        """从 Locator 读取文本列表，将卡片所有有效行用 ' | ' 拼接后返回。

        模型列表卡片的 inner_text 包含多行（序号 + 标题 + 下载数 + 收益区间 + 按钮），
        过滤掉固定按钮/标签文字后，将剩余行合并为一条可读字符串，例如：
          "1 | 法式复古客餐厅 | 109216 | 172-222元"

        Args:
            max_items: 最多读取条数；0（默认）表示全部读取，>0 则最多取该数量。
        Returns:
            非空文本列表（每条保留全部有效行）。失败返回空列表。
        """
        try:
            total = locator.count()
            count = total if max_items == 0 else min(total, max_items)
            results = []
            for i in range(count):
                raw = locator.nth(i).inner_text(timeout=3000)  # type: ignore[attr-defined]
                lines = [
                    line.strip()
                    for line in raw.split("\n")
                    if line.strip() and line.strip() not in self._SKIP_TEXTS
                ]
                results.append(" | ".join(lines) if lines else raw.strip())
            return results
        except Exception:
            return []

    def get_su_model_items_texts(self, max_items: int = 0) -> List[str]:
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
        """返回当前激活 Tab 的文本，自动 strip 空白（避免前后空格/换行导致精确匹配失败）。"""
        active_tab = self.get_locator("active_item")
        return (active_tab.text_content() or "").strip()

    def click_cad_go_create_and_switch(self) -> "Page":
        """点击 CAD Tab 下「去创作」按钮，切换到新 Tab 并返回新 Page 对象。

        目标 URL 为 upload?classifyType=3（CAD图纸品类被预选）。
        调用方断言完毕后调用 close_current_and_switch_to_original 回到原页面。
        """
        self.switch_to_new_tab(
            self.get_locator("cad_go_create_button").first,
            timeout=30000,
            wait_state="domcontentloaded",
            click_kwargs={"force": True},
        )
        self.page.wait_for_timeout(2000)
        return self.page

    def click_main_tab(self, name: str) -> None:
        """切换主 Tab（为你精选 / 3D模型 / SU模型 / CAD图纸）。

        使用 get_by_role("tab") 精确匹配，点击后等待 React 重新渲染列表数据。
        """
        self.page.get_by_role("tab", name=name, exact=True).click()
        self.wait.wait_for_timeout(2000)

    def get_current_tab_items_texts(self, max_items: int = 0) -> List[str]:
        """获取当前激活主 Tab 的模型列表文本。

        各主 Tab（为你精选/3D模型/SU模型/CAD图纸）共享同一 listItem CSS 类，
        复用 get_su_model_items_texts 即可。max_items=0 表示全部读取。
        """
        return self.get_su_model_items_texts(max_items=max_items)

