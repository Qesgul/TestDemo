"""
定价采集页面 Page Object — 切换模型、采集价格、拦截 API。

覆盖范围：
- 模型选择器展开 / 点击 / 切换
- 价格数字采集（右下角）
- 知点余额采集（右上角）
- aiDrawPrice 接口拦截与数据捕获

URL: https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=agent

元素 YAML：pages/elements/pricing_capture_elements.yaml
  - 所有 selector 均使用 [class*="xxx"] 模糊匹配，规避 CSS Modules 动态 hash
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
_KEY_MODEL_WRAPPER = "model_selector_wrapper"
_KEY_MODEL_PANEL = "model_dropdown_panel"
_KEY_MODEL_OPTION = "model_option_item"
_KEY_MODEL_TITLE = "model_option_title"
_KEY_MODEL_DESC = "model_option_desc"
_KEY_MODEL_ACTIVE_ICON = "model_active_icon"
_KEY_PRICE_NUM = "price_number"
_KEY_PRICE_TAG = "price_tag_container"
_KEY_STATUS_BAR = "status_bar"
_KEY_COIN_BALANCE = "coin_balance"

# ── API 拦截目标 ──────────────────────────────────────────────────────────────
_TARGET_API = "aiDrawPrice"


class PricingCapturePage(BasePage):
    """定价采集页面操作类（切换模型 → 采集价格 → 拦截接口）。"""

    DEFAULT_URL = (
        "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=agent"
    )

    def __init__(self, page: Page, auto_close_popups: bool = True) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/pricing_capture_elements.yaml",
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

    def goto(
        self,
        url: Optional[str] = None,
        close_popups_after_load: bool = True,
        wait_state: str = "domcontentloaded",
    ) -> None:
        """进入定价采集页面（agent 模式）。

        直接导航到 agent 页，保留 URL 验证和弹窗清理。
        """
        target_url = url or self.DEFAULT_URL

        # 直接导航到 agent 页
        super().goto(target_url, close_popups_after_load=False, wait_state=wait_state)
        self.page.wait_for_timeout(3000)

        # URL 验证
        if "menuKey=agent" not in self.page.url:
            _logger.warning(
                "导航后未到达 agent 页（当前 %s），清理弹窗后重试",
                self.page.url,
            )
            self.close_all_popups(max_tries=2)
            self.page.evaluate("""() => {
                document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
                document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            }""")
            self.page.wait_for_timeout(500)
            self.page.goto(target_url, wait_until=wait_state, timeout=20_000)
            self.page.wait_for_timeout(3000)

            if "menuKey=agent" not in self.page.url:
                raise RuntimeError(
                    f"导航到 agent 页失败，当前 URL: {self.page.url}。"
                    "请检查登录态或弹窗处理。"
                )

        _logger.info("goto 完成，当前 URL: %s", self.page.url)

        # 弹窗清理
        self.page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
        }""")
        self.page.wait_for_timeout(300)

        # 等待模型选择器可见
        self.get_locator(_KEY_MODEL_WRAPPER).first.wait_for(
            state="visible", timeout=15_000
        )

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
                ((body or {}).get("data") or {}).get("amount", "?"),
            )
            route.fulfill(response=response)

        self.page.route(f"**/{_TARGET_API}**", _handle_route)

    @property
    def api_captured(self) -> List[Dict[str, Any]]:
        """返回已捕获的 API 请求列表（只读）。"""
        return list(self._api_captured)

    # ===== 模型切换（业务操作） =====

    def get_model_count(self) -> int:
        """展开下拉，返回可用模型数量。"""
        self._open_model_dropdown()
        options = self.get_locator(_KEY_MODEL_OPTION)
        count = options.count()
        self._close_dropdown()
        return count

    def get_model_info(self, index: int) -> Dict[str, str]:
        """获取指定索引模型的名称和描述。

        :param index: 模型索引（从 0 开始）
        :return: {"name": "GPT Image 2", "desc": "更懂复杂指令..."}
        """
        self._open_model_dropdown()
        options = self.get_locator(_KEY_MODEL_OPTION)
        option = options.nth(index)
        option.wait_for(state="visible", timeout=5000)

        title_el = option.locator('[class*="modeTitle"]')
        desc_el = option.locator('[class*="modeDesc"]')

        name = title_el.inner_text().strip() if title_el.count() > 0 else ""
        desc = desc_el.inner_text().strip() if desc_el.count() > 0 else ""

        self._close_dropdown()
        return {"name": name, "desc": desc}

    def get_all_model_info(self) -> List[Dict[str, str]]:
        """一次性获取所有模型的名称和描述。"""
        self._open_model_dropdown()
        panel = self.get_locator(_KEY_MODEL_PANEL).first
        options = panel.locator('[class*="mode__"]')
        count = options.count()
        results = []
        for i in range(count):
            option = options.nth(i)
            title_el = option.locator('[class*="modeTitle"]')
            desc_el = option.locator('[class*="modeDesc"]')
            name = title_el.inner_text().strip() if title_el.count() > 0 else ""
            desc = desc_el.inner_text().strip() if desc_el.count() > 0 else ""
            # 正确的选中态判断：检查容器 class 是否含 "active"
            opt_class = option.get_attribute("class") or ""
            is_active = "active" in opt_class.lower()
            results.append({
                "index": i,
                "name": name,
                "desc": desc,
                "is_active": is_active,
            })
        self._close_dropdown()
        return results

    def switch_to_model(self, index: int, max_retries: int = 2) -> None:
        """切换到指定索引的模型。

        如果目标模型已是当前选中态则跳过点击。
        切换后通过下拉面板中的 active class 验证，未生效则重试。
        """
        for attempt in range(max_retries):
            self._open_model_dropdown()
            panel = self.get_locator(_KEY_MODEL_PANEL).first
            options = panel.locator('[class*="mode__"]')
            target = options.nth(index)
            target.wait_for(state="visible", timeout=5000)

            # 正确的选中态判断：检查容器 class 是否含 "active"
            opt_class = target.get_attribute("class") or ""
            if "active" in opt_class.lower():
                _logger.info("Model %d already active, skip click", index)
                self._close_dropdown()
                return

            target.click()
            self.page.wait_for_timeout(2000)

            # 验证：重新打开下拉，检查目标选项是否有 active class
            self._open_model_dropdown()
            panel2 = self.get_locator(_KEY_MODEL_PANEL).first
            options2 = panel2.locator('[class*="mode__"]')
            target2 = options2.nth(index)
            try:
                target2.wait_for(state="visible", timeout=3000)
                new_class = target2.get_attribute("class") or ""
            except Exception:
                new_class = ""

            if "active" in new_class.lower():
                _logger.info("Model switch to index %d verified (active class)", index)
                self._close_dropdown()
                return

            _logger.warning(
                "Model switch attempt %d failed: target class '%s' has no active",
                attempt + 1, new_class,
            )
            self._close_dropdown()

        _logger.error("Model switch to index %d failed after %d attempts", index, max_retries)

    # ===== 价格采集（状态查询） =====

    def get_current_model_name(self) -> str:
        """获取当前选中的模型名称（从选择器标签读取）。"""
        wrapper = self.get_locator(_KEY_MODEL_WRAPPER).first
        wrapper.wait_for(state="visible", timeout=5000)
        return wrapper.inner_text().strip()

    def get_current_price(self) -> str:
        """获取当前显示的价格数字文本（右下角）。"""
        price_el = self.get_locator(_KEY_PRICE_NUM).first
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

    def capture_model_price(self, index: int) -> Dict[str, Any]:
        """切换到指定模型并采集完整价格信息。

        :return: {"model_name": ..., "model_desc": ..., "price_text": ...,
                  "price_value": ..., "coin_balance": ..., "api_responses": ...}
        """
        # 先获取模型信息
        model_info = self.get_model_info(index)
        api_count_before = len(self._api_captured)

        # 切换模型
        self.switch_to_model(index)

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

        # 关联切换后触发的 API 响应
        new_api = self._api_captured[api_count_before:]
        api_data = None
        if new_api:
            resp = new_api[-1].get("response_body")
            if resp and isinstance(resp, dict):
                api_data = resp.get("data")

        return {
            "model_index": index,
            "model_name": model_info["name"],
            "model_desc": model_info["desc"],
            "price_text": price_text,
            "price_value": price_value,
            "coin_balance": balance,
            "api_response": api_data,
            "capture_time": datetime.now().isoformat(),
        }

    def capture_all_models(self) -> List[Dict[str, Any]]:
        """遍历所有模型，逐个切换并采集价格。

        策略：
        1. 开一次下拉，获取所有模型信息 + 标记当前选中项
        2. 关闭下拉
        3. 先采集当前选中模型的价格（无需切换）
        4. 逐个切换到其他模型，采集价格和 API 响应

        下拉操作：1（读信息）+ N-1（切换非选中模型）= N 次，无冗余。

        :return: 每个模型的价格信息列表
        """
        # 第一步：开一次下拉，获取所有模型信息
        all_info = self.get_all_model_info()
        model_count = len(all_info)
        _logger.info("发现 %d 个模型，开始逐个采集", model_count)

        # 每个模型都显式切换（active 检测不可靠，不跳过）
        results = {}
        for idx in range(model_count):
            info = all_info[idx]
            api_count_before = len(self._api_captured)

            # 每个模型都切换（switch_to_model 内部有 active 跳过逻辑）
            self.switch_to_model(idx)

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

            results[idx] = {
                "model_index": idx,
                "model_name": info["name"],
                "model_desc": info["desc"],
                "price_text": price_text,
                "price_value": price_value,
                "coin_balance": balance,
                "api_response": api_data,
                "capture_time": datetime.now().isoformat(),
            }
            _logger.info(
                "模型 %d/%d: %s = %s",
                idx + 1, model_count, info["name"], price_text,
            )

        # 按原始顺序返回
        return [results[i] for i in range(model_count)]

    # ===== 内部方法 =====

    def _open_model_dropdown(self) -> None:
        """点击模型选择器展开下拉面板。

        goto() 已验证 URL，此处只做轻量检查。
        """
        if "menuKey=agent" not in self.page.url:
            raise RuntimeError(
                f"当前不在 agent 页（{self.page.url}），请先调用 goto()"
            )

        wrapper = self.get_locator(_KEY_MODEL_WRAPPER).first
        wrapper.wait_for(state="visible", timeout=10_000)
        wrapper.click()
        self.page.wait_for_timeout(1000)

    def _close_dropdown(self) -> None:
        """关闭下拉面板。

        优先用 Escape 键关闭（避免点击坐标误触页面元素导致 SPA 路由跳转）。
        若 Escape 无效，降级点击模型选择器本身（切换面板开关状态）。
        """
        # 方案 1：Escape 键
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 检查面板是否已关闭
        panel = self.get_locator(_KEY_MODEL_PANEL)
        try:
            if panel.first.is_visible(timeout=300):
                # 方案 2：点击模型选择器本身（toggle 关闭）
                wrapper = self.get_locator(_KEY_MODEL_WRAPPER).first
                if wrapper.is_visible(timeout=500):
                    wrapper.click()
                    self.page.wait_for_timeout(300)
        except Exception:
            pass
