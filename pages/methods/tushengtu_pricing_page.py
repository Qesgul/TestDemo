# -*- coding: utf-8 -*-
"""旧版图生图定价采集 Page Object。

页面 URL: https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=tushengtuPurpose
交互流程: 选择创作类型（家装/建筑）→ 选择子分类（创作渲染/精准渲染等）→ 读取价格
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pages.base_page import BasePage

_logger = logging.getLogger(__name__)

# 元素 YAML key 常量
_KEY_CREATIVE_TAB = "creative_type_tab"
_KEY_SUBCATEGORY_CARD = "subcategory_card"
_KEY_PRICE_NUMBER = "price_number"
_KEY_COIN_BALANCE = "coin_balance"

_BASE_URL = "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=tushengtuPurpose"

_JS_DISMISS_MODALS = """() => {
    document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
}"""

# 定义每个创作类型下的子分类
CATEGORY_SUBS: Dict[str, List[str]] = {
    "家装": ["创作渲染", "精准渲染", "平面填彩", "毛坯精装设计", "新房软装搭配", "旧房改造焕新"],
    "建筑": ["创作渲染", "精准渲染", "总平填彩", "实景改造", "环境生成器"],
}


class TushengtuPricingPage(BasePage):
    """旧版图生图定价采集页面对象。"""

    def __init__(self, page, *, auto_close_popups: bool = True):
        super().__init__(
            page,
            elements_yaml_path="pages/elements/tushengtu_pricing_elements.yaml",
            auto_close_popups=auto_close_popups,
        )
        self.auto_close_popups = auto_close_popups

    # ===== 导航 =====

    def goto(self) -> None:
        """导航到旧版图生图页面。"""
        self.page.goto(_BASE_URL, wait_until="domcontentloaded", timeout=30_000)
        self.page.wait_for_timeout(3000)
        if self.auto_close_popups:
            self._dismiss_modals()
        # 等待创作类型 tab 可见
        self.get_locator(_KEY_CREATIVE_TAB).first.wait_for(
            state="visible", timeout=15_000
        )
        _logger.info("goto 完成，当前 URL: %s", self.page.url)

    def _dismiss_modals(self) -> None:
        """通过 JS 移除所有 ant-modal 叠加层。"""
        self.page.evaluate(_JS_DISMISS_MODALS)

    # ===== 创作类型切换 =====

    def click_category(self, category: str) -> bool:
        """点击创作类型 tab（家装/工装/建筑/景观）。

        :return: 是否成功点击
        """
        clicked = self.page.evaluate("""(cat) => {
            const tabs = document.querySelectorAll('[class*="tabItem"] span');
            for (const t of tabs) {
                if (t.textContent.trim() === cat) {
                    t.parentElement.click();
                    return true;
                }
            }
            return false;
        }""", category)

        if clicked:
            self.page.wait_for_timeout(2000)
            if self.auto_close_popups:
                self._dismiss_modals()
            self.page.wait_for_timeout(500)
            _logger.info("已切换到创作类型: %s", category)
        else:
            _logger.warning("未找到创作类型: %s", category)
        return clicked

    # ===== 子分类切换 =====

    def click_subcategory(self, name: str) -> bool:
        """点击子分类卡片（创作渲染/精准渲染等）。

        通过 Walker 遍历 DOM 找到精确文本匹配的叶子节点，
        再向上找可点击的父元素（cardInfoName）。

        :return: 是否成功点击
        """
        result = self.page.evaluate("""(name) => {
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_ELEMENT
            );
            while (walker.nextNode()) {
                const el = walker.currentNode;
                if (el.children.length === 0 && el.textContent.trim() === name) {
                    let target = el;
                    for (let i = 0; i < 3; i++) {
                        if (target.className.includes('cardInfoName')
                            || target.className.includes('item')
                            || target.className.includes('option')) {
                            target.click();
                            return true;
                        }
                        if (target.parentElement) target = target.parentElement;
                    }
                    el.click();
                    return true;
                }
            }
            return false;
        }""", name)

        if result:
            self.page.wait_for_timeout(1500)
            if self.auto_close_popups:
                self._dismiss_modals()
            self.page.wait_for_timeout(500)
            _logger.info("已切换到子分类: %s", name)
        else:
            _logger.warning("未找到子分类: %s", name)
        return result

    # ===== 价格读取 =====

    def get_current_price(self) -> str:
        """读取当前显示的价格文本。"""
        el = self.get_locator(_KEY_PRICE_NUMBER).first
        try:
            el.wait_for(state="visible", timeout=5000)
            return el.inner_text().strip()
        except Exception:
            return ""

    def get_coin_balance(self) -> str:
        """读取知点余额。"""
        el = self.get_locator(_KEY_COIN_BALANCE).first
        try:
            el.wait_for(state="visible", timeout=5000)
            return el.inner_text().strip()
        except Exception:
            return ""

    # ===== 批量采集 =====

    def capture_all(self) -> List[Dict[str, Any]]:
        """遍历所有创作类型×子分类，采集价格。

        :return: 每个组合的价格信息列表
        """
        results = []

        for category, subs in CATEGORY_SUBS.items():
            _logger.info("=== 创作类型: %s ===", category)
            self.click_category(category)

            for sub in subs:
                self.click_subcategory(sub)

                price_text = self.get_current_price()
                price_value = None
                if price_text:
                    try:
                        price_value = int(price_text)
                    except ValueError:
                        pass

                balance = self.get_coin_balance()

                results.append({
                    "category": category,
                    "subcategory": sub,
                    "price_text": price_text,
                    "price_value": price_value,
                    "coin_balance": balance,
                    "capture_time": datetime.now().isoformat(),
                })
                _logger.info("  %s/%s: %s 知点", category, sub, price_text)

        return results
