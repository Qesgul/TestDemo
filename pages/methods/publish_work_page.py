"""
发布作品页 Page Object - 最小校验与返回创作中心
"""

from __future__ import annotations

from playwright.sync_api import Page

from pages.base_page import BasePage


class PublishWorkPage(BasePage):
    """发布作品页操作类"""

    def __init__(
        self,
        page: Page,
        auto_close_popups: bool = False,
    ) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/publish_work_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    def is_on_publish_page(self) -> bool:
        return self.get_current_url().__contains__("creatorCenter/upload")

    def is_cad_category_selected(self) -> bool:
        """校验上传页「CAD图纸」品类是否被预选（radio checked）。

        从创作灵感 CAD Tab 点击「去创作」跳入时，URL 携带 classifyType=3，
        页面应自动勾选 CAD图纸 radio。
        """
        try:
            radio = self.get_locator("cad_category_radio")
            return radio.is_checked(timeout=3000)
        except Exception:
            return False


    def back_to_creative_center(self) -> None:
        """返回创作中心。

        策略：
        1. 优先在其他标签页中寻找 creatorCenter 页（非 upload）→ 关闭当前发布页并切回；
        2. 若找不到独立的 creatorCenter 标签页（说明发布页是在 creatorCenter 同 tab 内导航），
           则直接 go_back()，恢复到导航前的 creatorCenter 视图。
        """
        context = self.page.context
        alive = [p for p in context.pages if not p.is_closed()]

        # 寻找已存在的 creatorCenter 独立标签页（不是 upload 也不是当前页）
        cc_tab = next(
            (
                p for p in alive
                if p is not self.page
                and "creatorCenter" in p.url
                and "upload" not in p.url
            ),
            None,
        )

        if cc_tab:
            # 有独立 creatorCenter 标签页：关闭当前发布页并切回
            if not self.page.is_closed():
                self.page.close()
            self.switch_to_page(cc_tab)
        else:
            # 发布页是在 creatorCenter tab 内同 tab 导航而来，直接后退
            try:
                self.page.go_back(wait_until="domcontentloaded", timeout=10000)
            except Exception:
                pass
        self.wait.wait_for_timeout(1000)

