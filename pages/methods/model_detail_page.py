"""3D 模型详情页 - 充值弹窗信息获取流程的 Page Object。

约定：
- DEFAULT_URL 唯一 URL 配置点；用例层一律 `model_page.goto()` 无参调用
- 接口 mock：`mock_user_pay_identity(data_value)` 拦截 userPayIdentityV2 接口
- 套餐信息：`get_recharge_packages()` 返回 List[RechargePackageInfo]（来自 data_types），
  不再 print 噪声，统一走 logger
- 元素 selector 由 pages/elements/model_detail_elements.yaml 提供
"""
from __future__ import annotations
import json
import logging
from typing import List, Optional

from playwright.sync_api import Page, Route

from pages.base_page import BasePage
from data_types.recharge_data_types import RechargePackageInfo, RechargeBonusItem

_logger = logging.getLogger(__name__)


class ModelDetailPage(BasePage):
    """3D 模型详情页 - 知末网 3D 模型详情页。"""

    # ── 唯一 URL 配置点 ────────────────────────────────────
    DEFAULT_URL = (
        "https://3d.znzmo.com/3dmoxing/1198790555.html"
        "?requestId=22a843f6-3354-4146-a7b2-23f5c56a2d3d"
    )

    # ── 接口路径（用于 mock）─────────────────────────────
    PAY_IDENTITY_API = "**/payCenter/pay/userPayIdentityV2"

    def __init__(self, page: Page, auto_close_popups: bool = False) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/model_detail_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    # ══════════════════════════════════════════════════════════
    # 导航入口
    # ══════════════════════════════════════════════════════════

    def goto(self, url: Optional[str] = None, **kwargs) -> None:
        """进入 3D 模型详情页（无参时使用 DEFAULT_URL）。"""
        super().goto(url or self.DEFAULT_URL, **kwargs)
        self.page.wait_for_timeout(5000)

    # ══════════════════════════════════════════════════════════
    # 接口 mock
    # ══════════════════════════════════════════════════════════

    def mock_user_pay_identity(self, data_value: int) -> None:
        """拦截 userPayIdentityV2 接口，让 `data` 字段返回指定值。

        必须在触发会调该接口的操作（点击充值/下载按钮）**之前**调用。

        :param data_value: 1-14，对应不同用户身份场景
        """
        def _handler(route: Route) -> None:
            try:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "error": {"errorCode": "0", "errorMsg": "ok"},
                        "data": data_value,
                    }),
                )
            except Exception as e:
                _logger.warning("mock fulfill 失败 data=%s: %s", data_value, e)
                route.continue_()

        self.page.route(self.PAY_IDENTITY_API, _handler)
        _logger.info("已 mock userPayIdentityV2 接口返回 data=%d", data_value)

    def unmock_user_pay_identity(self) -> None:
        """解除接口 mock（用于下一轮 data_value 切换前清理）。"""
        try:
            self.page.unroute(self.PAY_IDENTITY_API)
        except Exception as e:
            _logger.debug("unroute 失败（可能未注册）: %s", e)

    # ══════════════════════════════════════════════════════════
    # 充值/下载按钮交互
    # ══════════════════════════════════════════════════════════

    def click_recharge_button(self) -> None:
        """点击充值按钮，触发充值弹窗。"""
        self.get_locator("recharge_button").first.click(force=True)
        self.wait.wait_for_timeout(2000)

    def click_download_button(self) -> None:
        """点击下载按钮，触发下载充值弹窗。"""
        self.get_locator("download_btn").first.click(force=True)
        self.wait.wait_for_timeout(2000)

    def is_recharge_modal_visible(self) -> bool:
        """充值弹窗是否可见。"""
        try:
            return self.get_locator("recharge_modal").is_visible()
        except Exception:
            return False

    def close_recharge_modal(self) -> None:
        """关闭充值弹窗（若可见）。

        点击充值弹窗关闭按钮后，页面可能弹出挽留弹窗，需一并关闭。
        """
        try:
            close_btn = self.get_locator("modal_close")
            if close_btn.is_visible():
                close_btn.click(force=True)
                self.wait.wait_for_timeout(1500)
        except Exception as e:
            _logger.debug("关闭充值弹窗失败: %s", e)

        try:
            retain_btn = self.get_locator("retention_modal_close")
            if retain_btn.is_visible():
                retain_btn.click(force=True)
                self.wait.wait_for_timeout(1000)
        except Exception as e:
            _logger.debug("关闭挽留弹窗失败（可能未出现）: %s", e)

    # ══════════════════════════════════════════════════════════
    # 充值套餐数据抓取
    # ══════════════════════════════════════════════════════════

    def get_recharge_packages(self) -> List[RechargePackageInfo]:
        """从充值弹窗抓取所有套餐信息。

        逐个点击套餐卡片，再读取卡片本身和弹窗底部的"实际支付/优惠"数值。

        :return: 套餐信息列表；弹窗未显示或解析失败时返回空列表
        """
        if not self.is_recharge_modal_visible():
            _logger.warning("充值弹窗未显示，无法抓取套餐信息")
            return []

        packages: List[RechargePackageInfo] = []
        try:
            self.get_locator("package_card").first.wait_for(state="visible", timeout=5000)
            cards = self.get_locator("package_card").all()
            _logger.info("找到 %d 个套餐卡片", len(cards))

            for card in cards:
                card.click()
                self.wait.wait_for_timeout(1000)

                name = self._safe_inner_text(card, "package_name")
                price = self._safe_inner_text(card, "package_price")
                discount = self._safe_inner_text(card, "package_discount")

                bonus_items: List[RechargeBonusItem] = []
                try:
                    for item in self.get_locator("bonus_item").all():
                        text = item.inner_text(timeout=1000).strip()
                        if text:
                            bonus_items.append(RechargeBonusItem(title=text))
                except Exception as e:
                    _logger.debug("加购福利读取失败: %s", e)

                remark = self._safe_page_text("package_remark")
                actual_pay = self._safe_page_text("actual_pay_price")
                actual_discount = self._safe_page_text("actual_discount_amount")

                packages.append(RechargePackageInfo(
                    package_name=name,
                    price=price,
                    package_discount=discount,
                    bonus_items=bonus_items,
                    package_remark=remark or None,
                    actual_pay_price=actual_pay or None,
                    actual_discount_amount=actual_discount or None,
                ))
        except Exception as e:
            _logger.warning("套餐信息抓取失败: %s", e)

        return packages

    # ══════════════════════════════════════════════════════════
    # 内部工具
    # ══════════════════════════════════════════════════════════

    def _safe_inner_text(self, parent, yaml_key: str) -> str:
        """从父 locator 内部按 YAML key 取文本，失败返回空字符串。"""
        try:
            selector = self._elements.get(yaml_key, "")
            if isinstance(selector, dict):
                selector = selector.get("selector", "")
            text = parent.locator(selector).inner_text(timeout=2000)
            return text.strip() if text else ""
        except Exception as e:
            _logger.debug("inner_text 失败 key=%s: %s", yaml_key, e)
            return ""

    def _safe_page_text(self, yaml_key: str) -> str:
        """从整个页面按 YAML key 取首个匹配元素的文本，失败返回空字符串。"""
        try:
            text = self.get_locator(yaml_key).first.inner_text(timeout=2000)
            return text.strip() if text else ""
        except Exception as e:
            _logger.debug("page text 失败 key=%s: %s", yaml_key, e)
            return ""
