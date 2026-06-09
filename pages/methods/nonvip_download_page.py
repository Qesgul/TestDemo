"""非VIP用户下载确认弹窗 - Page Object。

继承 ModelDetailPage，复用：
  - goto() / goto_model()              进入模型详情页
  - click_download_button()            点击「立即下载」（需 codegen 确认 sgt 站 selector 与 3d 站一致）
  - mock_user_pay_identity(data_value) 拦截 userPayIdentityV2 接口（BND-004 VIP mock 用）

本类追加：
  - wait_for_download_dialog()         等待下载确认弹窗出现
  - click_coupon(coupon_type)          点击指定面额的知币券单选框
  - is_coupon_selected(coupon_type)    券是否处于选中态
  - is_coupon_disabled(coupon_type)    券是否处于置灰/禁用态
  - get_selected_coupon_type()         返回当前默认选中的面额字符串
  - get_coupon_control_role()          返回券控件 ARIA role 属性
  - get_discount_amount_text()         读取「已优惠」金额文本
  - get_total_amount_text()            读取「总计应付」金额文本
  - get_detail_page_price_text()       读取详情页到手价文本（弹窗打开前调用）
  - parse_zhibi(text)                  从金额文本中提取知币整数

元素 selector 见 pages/elements/nonvip_download_elements.yaml（TODO_SELECTOR 待 codegen 回填）。
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from playwright.sync_api import Page

from common.yaml_loader import load_yaml
from pages.methods.model_detail_page import ModelDetailPage

_logger = logging.getLogger(__name__)


class NonvipDownloadPage(ModelDetailPage):
    """非VIP用户下载确认弹窗 - 基于 ModelDetailPage 扩展。"""

    # ── URL 配置（唯一入口，用例层只调 goto()）────────────────────────────────
    DEFAULT_URL = "https://sgt.znzmo.com/sgt/36982063.html"  # 60知币模型（主力）

    MODEL_URLS: dict[int, str] = {
        60: "https://sgt.znzmo.com/sgt/36982063.html",
        40: "https://sgt.znzmo.com/sgt/731308280.html",
        23: (
            "https://3d.znzmo.com/3dmoxing/1198790555.html"
            "?requestId=22a843f6-3354-4146-a7b2-23f5c56a2d3d"
        ),
    }

    _COUPON_RADIO_KEYS: dict[str, str] = {
        "35": "coupon_radio_35",
        "40": "coupon_radio_40",
        "5":  "coupon_radio_5",
    }

    def __init__(self, page: Page, auto_close_popups: bool = False) -> None:
        super().__init__(page=page, auto_close_popups=auto_close_popups)
        # 追加弹窗专用 selector，覆盖同名 key（如 download_btn 换为 sgt 站版本）
        dialog_elements = load_yaml("pages/elements/nonvip_download_elements.yaml")
        self._elements.update(dialog_elements)

    # ══════════════════════════════════════════════════════════════════════════
    # 导航入口
    # ══════════════════════════════════════════════════════════════════════════

    def goto_model(self, price: int) -> None:
        """按原价知币数切换测试模型（60 / 40 / 23 知币）。

        :param price: 60 / 40 / 23
        """
        url = self.MODEL_URLS.get(price)
        if not url:
            raise ValueError(
                f"未知 price={price!r}，仅支持 {list(self.MODEL_URLS.keys())}"
            )
        self.goto(url=url)

    # ══════════════════════════════════════════════════════════════════════════
    # 下载确认弹窗
    # ══════════════════════════════════════════════════════════════════════════

    def wait_for_download_dialog(self, timeout: int = 8000) -> None:
        """等待下载确认弹窗出现。"""
        self.get_locator("download_dialog").wait_for(state="visible", timeout=timeout)

    def is_download_dialog_visible(self) -> bool:
        """下载确认弹窗是否可见。"""
        try:
            return self.get_locator("download_dialog").is_visible(timeout=500)
        except Exception:
            return False

    def close_download_dialog(self) -> None:
        """关闭下载确认弹窗（若可见）。"""
        try:
            btn = self.get_locator("dialog_close")
            if btn.is_visible(timeout=500):
                btn.click(force=True)
                self.wait.wait_for_timeout(800)
        except Exception as e:
            _logger.debug("关闭下载弹窗失败: %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # 券交互
    # ══════════════════════════════════════════════════════════════════════════

    def click_coupon(self, coupon_type: str) -> None:
        """点击指定面额的知币券单选框，触发选中/取消选中。

        :param coupon_type: "35" / "40" / "5"
        """
        key = self._COUPON_RADIO_KEYS.get(coupon_type)
        if not key:
            raise ValueError(
                f"未知 coupon_type={coupon_type!r}，仅支持 '35' / '40' / '5'"
            )
        self.get_locator(key).click(force=True)
        self.wait.wait_for_timeout(500)

    def is_coupon_selected(self, coupon_type: str) -> bool:
        """判断指定面额知币券是否处于选中态（checked）。"""
        key = self._COUPON_RADIO_KEYS.get(coupon_type)
        if not key:
            return False
        try:
            radio = self.get_locator(key)
            checked = radio.is_checked()
            if checked:
                return True
            aria = radio.get_attribute("aria-checked")
            return aria == "true"
        except Exception as e:
            _logger.debug("is_coupon_selected(%s) 失败: %s", coupon_type, e)
            return False

    def is_coupon_disabled(self, coupon_type: str) -> bool:
        """判断指定面额知币券是否处于置灰/禁用态。"""
        key = self._COUPON_RADIO_KEYS.get(coupon_type)
        if not key:
            return False
        try:
            radio = self.get_locator(key)
            if radio.is_disabled():
                return True
            if radio.get_attribute("disabled") is not None:
                return True
            aria = radio.get_attribute("aria-disabled")
            return aria == "true"
        except Exception as e:
            _logger.debug("is_coupon_disabled(%s) 失败: %s", coupon_type, e)
            return False

    def get_selected_coupon_type(self) -> Optional[str]:
        """返回当前弹窗内默认选中的券面额字符串（'35'/'40'/'5'），无选中时返回 None。"""
        for coupon_type in ("35", "40", "5"):
            if self.is_coupon_selected(coupon_type):
                return coupon_type
        return None

    def get_coupon_control_role(self, coupon_type: str) -> str:
        """返回券控件的 ARIA role 属性值（用于 AUTO-CPN-003 验证 role=radio）。"""
        key = self._COUPON_RADIO_KEYS.get(coupon_type)
        if not key:
            return ""
        try:
            return self.get_locator(key).get_attribute("role") or ""
        except Exception as e:
            _logger.debug("get_coupon_control_role(%s) 失败: %s", coupon_type, e)
            return ""

    # ══════════════════════════════════════════════════════════════════════════
    # 金额读取
    # ══════════════════════════════════════════════════════════════════════════

    def get_discount_amount_text(self) -> str:
        """获取「已优惠」金额文本（原始字符串，含「知币」单位）。"""
        try:
            return self.get_locator("discount_amount").inner_text(timeout=3000).strip()
        except Exception as e:
            _logger.debug("get_discount_amount_text 失败: %s", e)
            return ""

    def get_total_amount_text(self) -> str:
        """获取「总计应付」金额文本（原始字符串，含「知币」单位）。"""
        try:
            return self.get_locator("total_amount").inner_text(timeout=3000).strip()
        except Exception as e:
            _logger.debug("get_total_amount_text 失败: %s", e)
            return ""

    def get_detail_page_price_text(self) -> str:
        """获取详情页「到手价」文本（弹窗打开前调用，用于 AUTO-CAL-003 一致性比对）。"""
        try:
            return self.get_locator("detail_page_price").inner_text(timeout=3000).strip()
        except Exception as e:
            _logger.debug("get_detail_page_price_text 失败: %s", e)
            return ""

    @staticmethod
    def parse_zhibi(text: str) -> int:
        """从金额文本中提取知币整数，取第一个数字序列。

        示例: "35 知币" → 35 ; "已优惠 0 知币" → 0 ; "" → 0
        """
        nums = re.findall(r"\d+", text)
        return int(nums[0]) if nums else 0
