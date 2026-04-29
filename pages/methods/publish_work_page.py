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


    def back_to_creative_center(self) -> None:
        """返回创作中心"""
        self.page.go_back()
        self.wait.wait_for_timeout(2000)

