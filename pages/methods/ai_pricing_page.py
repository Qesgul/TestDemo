"""
AI 定价采集 Page Object（统一版）— 平面填彩 / 实景改造 / 全景渲染。

这三个页面结构完全相同（BottomPartButtons 模式切换），只是 menuKey 和
subServiceType 不同，因此合并为一个参数化 Page Object。

覆盖范围：
- 模式切换：BottomPartButtons modeText → popover → modeTitle 选项
- 价格采集：生成按钮上的知点数（zdIconText）
- 知点余额：右上角（zidianAmount）
- aiDrawPrice 接口拦截与数据捕获

页面路由：
  平面填彩   → menuKey=floorPlanColor
  实景改造   → menuKey=insituRenovation
  全景渲染   → 需从左侧菜单点击进入（goto 会被重定向到 home）

弹窗处理：
  统一用 JS 移除 ant-modal DOM。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from pages.base_page import BasePage, PopupStrategy

_logger = logging.getLogger(__name__)

# ── YAML 键名常量 ─────────────────────────────────────────────────────────────
_KEY_MODE_TEXT_BUTTON = "mode_text_button"
_KEY_MODE_POPOVER = "mode_popover"
_KEY_MODE_TITLE = "mode_title"
_KEY_ZD_ICON_TEXT = "zd_icon_text"
_KEY_COIN_BALANCE = "coin_balance"
_KEY_MENU_ITEM = "menu_item"

# ── 产品定义 ─────────────────────────────────────────────────────────────────
PRODUCTS = {
    "平面填彩": {
        "menu_key": "floorPlanColor",
        "sub_modes": ["标准模式", "Nano Banana Pro", "GPT Image 2"],
    },
    "实景改造": {
        "menu_key": "insituRenovation",
        "sub_modes": ["标准模式", "Nano Banana Pro"],
    },
    "全景渲染": {
        "menu_key": "panoramicRender",
        "sub_modes": [],  # 待探索
        "navigate_via_menu": True,  # goto 会被重定向，需从左侧菜单进入
    },
}

# ── API 拦截目标 ──────────────────────────────────────────────────────────────
_TARGET_API = "aiDrawPrice"

# ── JS 工具函数 ───────────────────────────────────────────────────────────────
_JS_DISMISS_MODALS = """() => {
    document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
}"""


class AIPricingPage(BasePage):
    """AI 定价采集页面操作类（统一版：平面填彩 / 实景改造 / 全景渲染）。"""

    BASE_URL = "https://ai.znzmo.cn/community/AIDrawPage.html"
    HOME_URL = "https://ai.znzmo.cn/community/AIDrawPage.html"

    def __init__(self, page: Page, auto_close_popups: bool = True) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/ai_pricing_elements.yaml",
            auto_close_popups=auto_close_popups,
        )
        # 接口拦截缓存
        self._api_captured: List[Dict[str, Any]] = []

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        """处理 AI 页面特有的延迟弹窗。"""
        return [
            PopupStrategy(
                name="ai_draw_plugin_modal",
                trigger_selector="[class*='aiDrawAdForPluginModal']",
                close_selector=(
                    "[class*='leftBtn'], .ant-modal-close, "
                    "[class*='closeIcon'], [class*='CloseIcon']"
                ),
            ),
        ]

    # ===== 页面导航 =====

    def goto_page(self, menu_key: str, navigate_via_menu: bool = False) -> None:
        """导航到指定 menuKey 页面。

        SPA 页面首次加载时价格可能为默认值（如 batchSize=2 对应 8 知点），
        需要 reload 一次让页面完全初始化后再读取正确价格。

        :param menu_key: URL 参数值（floorPlanColor / insituRenovation / panoramicRender）
        :param navigate_via_menu: True 则从左侧菜单进入（全景渲染需此方式）
        """
        if navigate_via_menu:
            self._navigate_via_menu(menu_key)
        else:
            target_url = f"{self.BASE_URL}?menuKey={menu_key}"

            # 直接导航
            self.page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
            self.page.wait_for_timeout(2000)

            # URL 验证
            if f"menuKey={menu_key}" not in self.page.url:
                _logger.warning(
                    "导航后未到达 %s 页（当前 %s），清理弹窗后重试",
                    menu_key, self.page.url,
                )
                self._dismiss_modals()
                self.page.wait_for_timeout(500)
                self.page.goto(target_url, wait_until="domcontentloaded", timeout=20_000)
                self.page.wait_for_timeout(2000)

                if f"menuKey={menu_key}" not in self.page.url:
                    raise RuntimeError(
                        f"导航到 {menu_key} 页失败，当前 URL: {self.page.url}。"
                        "请检查登录态或弹窗处理。"
                    )

            # SPA 首次加载时价格可能为默认值（batchSize=2），reload 一次
            # 让页面完全初始化以获取正确价格（batchSize=4，价格=16）
            self._dismiss_modals()
            self.page.wait_for_timeout(300)
            self.page.reload(wait_until="domcontentloaded", timeout=20_000)
            self.page.wait_for_timeout(3000)

        _logger.info("goto_page 完成，当前 URL: %s", self.page.url)

        # 弹窗清理
        self._dismiss_modals()
        self.page.wait_for_timeout(300)

        # 等待模式切换按钮可见（页面加载完成标志）
        self._wait_for_page_ready()

    def _navigate_via_menu(self, menu_key: str) -> None:
        """从左侧菜单点击进入页面（用于全景渲染等无法直接 goto 的页面）。"""
        # 先到 home 页
        super().goto(self.HOME_URL, close_popups_after_load=False, wait_state="domcontentloaded")
        self.page.wait_for_timeout(3000)
        self._dismiss_modals()
        self.page.wait_for_timeout(500)

        # 确定菜单文本
        menu_text_map = {
            "panoramicRender": "全景渲染",
        }
        menu_text = menu_text_map.get(menu_key, menu_key)

        # 从左侧菜单点击
        _logger.info("通过左侧菜单 '%s' 进入页面", menu_text)

        # 尝试多种选择器
        clicked = False
        selectors = [
            f'[class*="customMenuItem"]:has-text("{menu_text}")',
            f'li:has-text("{menu_text}")',
        ]
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=3000):
                    # 使用 JS 点击绕过可能的叠加层
                    self.page.evaluate("""(text) => {
                        const items = document.querySelectorAll('[class*="customMenuItem"]');
                        for (const item of items) {
                            if (item.textContent.includes(text) || item.innerText.includes(text)) {
                                item.click();
                                return true;
                            }
                        }
                        const lis = document.querySelectorAll('li');
                        for (const li of lis) {
                            if (li.textContent.includes(text) || li.innerText.includes(text)) {
                                li.click();
                                return true;
                            }
                        }
                        return false;
                    }""", menu_text)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            raise RuntimeError(f"未找到左侧菜单项 '{menu_text}'，请检查页面结构")

        self.page.wait_for_timeout(3000)
        self._dismiss_modals()
        self.page.wait_for_timeout(500)

    def _wait_for_page_ready(self) -> None:
        """等待页面加载完成（价格元素或模式切换按钮可见）。"""
        try:
            self.get_locator(_KEY_ZD_ICON_TEXT).first.wait_for(
                state="visible", timeout=15_000
            )
        except Exception:
            # 如果价格不可见，至少等模式按钮
            try:
                self.get_locator(_KEY_MODE_TEXT_BUTTON).first.wait_for(
                    state="visible", timeout=10_000
                )
            except Exception:
                _logger.warning("页面可能未完全加载，价格和模式按钮均不可见")

    # ===== API 拦截 =====

    def enable_api_intercept(self) -> None:
        """启用 aiDrawPrice 接口拦截，捕获请求与响应。"""
        self._api_captured.clear()

        def _handle_route(route):
            request = route.request
            response = route.fetch()

            try:
                body = response.json()
            except Exception:
                body = None

            entry = {
                "timestamp": datetime.now().isoformat(),
                "url": request.url,
                "method": request.method,
                "request_body": None,
                "response_status": response.status,
                "response_body": body,
            }
            post_data = request.post_data
            if post_data:
                try:
                    entry["request_body"] = json.loads(post_data)
                except Exception:
                    entry["request_body"] = post_data

            self._api_captured.append(entry)
            _logger.info(
                "API intercepted: amount=%s",
                (body or {}).get("data", {}).get("amount", "?"),
            )
            route.fulfill(response=response)

        self.page.route(f"**/{_TARGET_API}**", _handle_route)

    @property
    def api_captured(self) -> List[Dict[str, Any]]:
        """返回已捕获的 API 请求列表（只读）。"""
        return list(self._api_captured)

    # ===== 弹窗处理 =====

    def _dismiss_modals(self) -> None:
        """通过 JS 移除所有 ant-modal 叠加层。"""
        self.page.evaluate(_JS_DISMISS_MODALS)

    # ===== 子模式切换（BottomPartButtons modeText）=====

    def get_sub_modes_from_ui(self) -> List[str]:
        """读取 modeText 按钮当前文本，返回当前显示的子模式名称。"""
        try:
            mode_text_btn = self.get_locator(_KEY_MODE_TEXT_BUTTON).first
            mode_text_btn.wait_for(state="visible", timeout=5000)
            return [mode_text_btn.inner_text().strip()]
        except Exception:
            return []

    def get_current_sub_mode_name(self) -> str:
        """获取当前显示的子模式名称（从 modeText 按钮读取）。"""
        try:
            mode_text_btn = self.get_locator(_KEY_MODE_TEXT_BUTTON).first
            mode_text_btn.wait_for(state="visible", timeout=5000)
            return mode_text_btn.inner_text().strip()
        except Exception:
            return ""

    def switch_sub_mode(self, mode_name: str) -> bool:
        """通过 modeText 按钮切换子模式，并等待价格稳定。

        使用 Playwright locator 原生点击（比 JS eval 更可靠地触发 SPA 事件）。
        切换后轮询价格直到稳定，确保 API 更新已完成。

        :param mode_name: 目标子模式名称（如 "标准模式" 或 "Nano Banana Pro"）
        :return: 是否成功切换
        """
        mode_text_btn = self.get_locator(_KEY_MODE_TEXT_BUTTON).first
        try:
            mode_text_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            _logger.warning("modeText 按钮不可见，当前页面可能不支持子模式切换")
            return False

        # 记录切换前的价格
        price_before = self.get_current_price()

        # 1. 点击 modeText 按钮，触发 popover（使用 Playwright 原生点击）
        try:
            mode_text_btn.click(force=True)
        except Exception:
            # 兜底：JS 点击
            self.page.evaluate("""() => {
                const btn = document.querySelector('[class*="modeText"]');
                if (btn) btn.click();
            }""")
        self.page.wait_for_timeout(1000)

        # 2. 在 popover 中找到匹配的选项并点击（Playwright locator）
        #    先尝试 locator API，兜底用 JS
        option_selector = f'[class*="modeTitle"]:has-text("{mode_name}")'
        option = self.page.locator(option_selector).first
        try:
            option.wait_for(state="visible", timeout=3000)
            # 点击选项的可点击容器（modeTitle 的父级行）
            option.evaluate("""(el) => {
                const clickable = el.closest('[class*="mode__"]') || el.parentElement || el;
                clickable.click();
            }""")
        except Exception:
            _logger.warning("未找到子模式选项: %s，尝试兜底方案", mode_name)
            # 兜底：JS 全局搜索
            clicked = self.page.evaluate("""(modeName) => {
                const titles = document.querySelectorAll('[class*="modeTitle"]');
                for (const t of titles) {
                    if (t.textContent.trim().includes(modeName) || t.innerText.trim().includes(modeName)) {
                        const clickable = t.closest('[class*="mode__"]') || t.parentElement || t;
                        clickable.click();
                        return true;
                    }
                }
                return false;
            }""", mode_name)
            if not clicked:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)
                return False

        # 3. 等待价格更新完成
        self.page.wait_for_timeout(2000)
        self._dismiss_modals()
        self.page.wait_for_timeout(300)

        price_after = self.get_current_price()
        _logger.info("已切换到子模式: %s, 价格: %s → %s", mode_name, price_before, price_after)
        return True

    # ===== 价格采集 =====

    def get_current_price(self) -> str:
        """获取当前显示的价格数字文本（生成按钮上的知点数）。"""
        price_el = self.get_locator(_KEY_ZD_ICON_TEXT).first
        try:
            price_el.wait_for(state="visible", timeout=5000)
            return price_el.inner_text().strip()
        except Exception:
            return ""

    def get_coin_balance(self) -> str:
        """获取右上角知点余额。"""
        balance_el = self.get_locator(_KEY_COIN_BALANCE).first
        try:
            balance_el.wait_for(state="visible", timeout=5000)
            return balance_el.inner_text().strip()
        except Exception:
            return ""

    # ===== 组合采集 =====

    def capture_sub_mode_price(self, sub_mode_name: str) -> Dict[str, Any]:
        """切换到指定子模式并采集价格。

        :param sub_mode_name: 子模式名称（如 "标准模式"、"Nano Banana Pro"）
        :return: 价格信息字典
        """
        api_count_before = len(self._api_captured)

        # 切换子模式
        self.switch_sub_mode(sub_mode_name)

        # 采集价格
        price_text = self.get_current_price()
        price_value = None
        if price_text:
            try:
                price_value = int(price_text)
            except ValueError:
                pass

        # 采集余额
        balance = self.get_coin_balance()

        # 关联 API 响应
        new_api = self._api_captured[api_count_before:]
        api_data = None
        if new_api:
            resp = new_api[-1].get("response_body")
            if resp and isinstance(resp, dict):
                api_data = resp.get("data")

        return {
            "sub_mode": sub_mode_name,
            "price_text": price_text,
            "price_value": price_value,
            "coin_balance": balance,
            "api_response": api_data,
            "capture_time": datetime.now().isoformat(),
        }

    def capture_all_sub_modes(self, product_name: str, sub_modes: List[str]) -> List[Dict[str, Any]]:
        """遍历所有子模式并采集价格。

        :param product_name: 产品名（如 "平面填彩"）
        :param sub_modes: 子模式名称列表（如 ["标准模式", "Nano Banana Pro", "GPT Image 2"]）
        :return: 每个子模式的价格信息列表
        """
        results = []

        for sm in sub_modes:
            _logger.info("采集 %s × %s", product_name, sm)
            api_count_before = len(self._api_captured)

            self.switch_sub_mode(sm)

            price_text = self.get_current_price()
            price_value = None
            if price_text:
                try:
                    price_value = int(price_text)
                except ValueError:
                    pass

            balance = self.get_coin_balance()

            new_api = self._api_captured[api_count_before:]
            api_data = None
            if new_api:
                resp = new_api[-1].get("response_body")
                if resp and isinstance(resp, dict):
                    api_data = resp.get("data")

            results.append({
                "product": product_name,
                "sub_mode": sm,
                "price_text": price_text,
                "price_value": price_value,
                "coin_balance": balance,
                "api_response": api_data,
                "capture_time": datetime.now().isoformat(),
            })
            _logger.info("采集 %s × %s = %s 知点", product_name, sm, price_text)

        return results

    def discover_sub_modes(self) -> List[str]:
        """尝试通过 UI 发现当前页面的可用子模式。

        打开 popover 后读取所有 modeTitle 选项的文本。
        """
        # 点击 modeText 按钮，触发 popover
        self.page.evaluate("""() => {
            const btn = document.querySelector('[class*="modeText"]');
            if (btn) btn.click();
        }""")
        self.page.wait_for_timeout(1000)

        # 读取所有 modeTitle 文本
        modes = self.page.evaluate("""() => {
            const titles = document.querySelectorAll('[class*="modeTitle"]');
            return Array.from(titles).map(t => t.textContent.trim()).filter(t => t.length > 0);
        }""")

        # 关闭 popover
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

        _logger.info("发现子模式: %s", modes)
        return modes if modes else []
