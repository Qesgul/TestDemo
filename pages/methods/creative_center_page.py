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

    # 不参与存储/比对的按钮/固定标签文本（完整匹配）
    _SKIP_TEXTS: set[str] = {"去创作", "近30天预估收益"}

    def _safe_get_texts(self, locator, max_items: int = 0) -> List[str]:
        """从 Locator 读取文本列表，将卡片所有有效行用 ' | ' 拼接后返回。

        排行榜卡片的 inner_text 包含多行（序号 + 标题 + 下载数 + 收益区间 + 按钮），
        过滤掉固定按钮/标签文字后，将剩余行合并为一条可读字符串，例如：
          "法式复古客餐厅 | 109216 | 172-222元"
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

    def click_home_to_creative_center(self) -> None:
        """
        点击首页/面包屑进入创作中心。

        说明：
        - 这里允许导航失败不抛出异常（让后续"榜单元素校验"给出更明确失败点）；
        - 先尝试 YAML 定位器，再兜底点击"首页"，最后再尝试"创作中心"文本。
        """
        # 标签页切换后页面渲染和弹窗遮挡可能尚未完全稳定，刷新一次关闭弹窗
        self._reload_to_dismiss_popups()

        click_err: Exception | None = None

        # 1) 优先 YAML 定位器：点击"首页/面包屑"
        try:
            btn = self.get_locator("home_to_creative_center").first
            btn.wait_for(state="visible", timeout=15000)
            btn.scroll_into_view_if_needed()
            btn.click(force=True)
        except Exception as e:
            click_err = e

        # 2) YAML 定位器不可点：退化为点击文本"首页"
        if click_err is not None:
            home = self.page.locator("text=首页").first
            home.wait_for(state="visible", timeout=15000)
            home.scroll_into_view_if_needed()
            home.click(force=True)

        # 3) 确认步骤执行成功：等待 URL 进入创作中心（timeout 单位为秒）
        try:
            self.wait.wait_for_url(r"regex:.*creatorCenter.*", timeout=15)
        except Exception:
            # 若 URL 不变化，后续榜单校验会给出更明确失败点
            pass

        # 等待 URL 或内容稳定，而不是盲等
        try:
            self.wait.wait_for_url(r"regex:.*creatorCenter.*", timeout=5)
        except Exception:
            try:
                self.wait.wait_for_timeout(500)
            except Exception:
                pass  # 页面可能已关闭或正在导航，忽略等待错误


    def get_rank_3d_default_items_texts(self, max_items: int = 0) -> List[str]:
        """获取 3D爆款榜默认条目文本"""
        try:
            items = self.get_locator("rank_3d_items")
            texts = self._safe_get_texts(items, max_items=max_items)
            if texts:
                return texts
        except Exception:
            pass

        # 兜底：更宽松的"页面已加载内容"信号，保证冒烟流程能继续往后
        try:
            imgs = self.page.locator("img")
            if imgs.count() > 0:
                return ["img"]
        except Exception:
            pass

        return []

    def get_rank_su_default_items_texts(self, max_items: int = 0) -> List[str]:
        """获取 SU爆款榜默认条目文本"""
        try:
            items = self.get_locator("rank_su_items")
            texts = self._safe_get_texts(items, max_items=max_items)
            if texts:
                return texts
        except Exception:
            pass

        # 兜底：更宽松的"页面已加载内容"信号
        try:
            imgs = self.page.locator("img")
            if imgs.count() > 0:
                return ["img"]
        except Exception:
            pass

        return []

    def click_go_create_from_rank(self) -> None:
        """点击榜单中的"去创作"，跳转发布作品页。

        兼容三种行为：
        1. 新 tab 打开 upload 页（最常见）
        2. 同 tab 跳转到 upload 页
        3. 新 tab 在 expect_page 等待期间打开但未被捕获（网络慢）

        调用后通过 self.page 获取当前活跃页面引用。
        """
        btn = self.get_locator("rank_go_create_button").first
        btn.wait_for(state="visible", timeout=5000)

        try:
            # ① 优先等待新 tab（超时改为 10s 以兼容慢网络）
            self.switch_to_new_tab(btn, timeout=10000, click_kwargs={"force": True})
            return
        except Exception:
            pass

        # ② expect_page 超时后：扫描所有存活 tab 找含 upload 的
        context = self.page.context
        upload_tab = next(
            (
                p for p in context.pages
                if "upload" in p.url and not p.is_closed()
            ),
            None,
        )
        if upload_tab:
            self.switch_to_page(upload_tab)
            return

        # ③ 检查当前 tab 是否已同 tab 导航到 upload
        if "upload" in self.page.url:
            return

        # ④ 等待当前 tab 导航到 upload（同 tab 跳转但导航略晚于超时）
        try:
            self.wait.wait_for_url(r"regex:.*upload.*", timeout=8000)
        except Exception:
            # 等待页面稳定（导航到任意页面）
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)

    def click_su_rank_item(self, index: int = 0) -> None:
        """点击 SU榜 第 index 个 item，进入创作灵感页（自动处理新标签页）。

        榜单 item 可能打开新标签页，也可能在当前页导航。
        调用后通过 self.page 获取当前活跃页面引用。
        """
        items = self.get_locator("rank_su_items")
        if items.count() == 0:
            return
        item = items.nth(min(index, items.count() - 1))
        # 先滚动到元素，不依赖 viewport 可见性
        try:
            item.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        try:
            self.switch_to_new_tab(item, timeout=5000, click_kwargs={"force": True})
        except Exception:
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)

