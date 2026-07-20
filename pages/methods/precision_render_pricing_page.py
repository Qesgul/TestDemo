"""
精准渲染定价采集 Page Object — 切换创作模式×DeepMode，采集价格，拦截 API。

覆盖范围：
- 创作模式 radio 按钮切换（精准渲染 / 创作渲染 / 效果图美化）
- DeepMode 面板展开 / 点击 / 切换（仅精准渲染页有 DeepMode）
- 价格数字采集（生成按钮上的知点数）
- 知点余额采集（右上角）
- aiDrawPrice 接口拦截与数据捕获

页面路由：
  精准渲染 → menuKey=precisionRender  （有 DeepMode）
  创作渲染 → menuKey=ideaRender       （无 DeepMode）
  效果图美化 → menuKey=imageEnhancement （无 DeepMode）

元素 YAML：pages/elements/precision_render_pricing_elements.yaml
  - 所有 selector 均使用 [class*="xxx"] 模糊匹配，规避 CSS Modules 动态 hash

弹窗处理：
  切换创作模式和 DeepMode 时会触发 PrecisionRenderUpgradeModal 升级弹窗，
  该弹窗使用 ant-modal 叠加层拦截所有指针事件。
  策略：所有交互均通过 JS dispatchEvent 绕过叠加层拦截，
  操作后统一用 JS 移除弹窗 DOM。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from common.pricing_helpers import parse_price
from pages.base_page import BasePage, PopupStrategy

_logger = logging.getLogger(__name__)

# ── YAML 键名常量 ─────────────────────────────────────────────────────────────
_KEY_RADIO_ITEM = "radio_item"
_KEY_DEEP_MODE_TRIGGER = "deep_mode_trigger"
_KEY_DEEP_MODE_PANEL = "deep_mode_panel"
_KEY_DEEP_MODE_OPTION = "deep_mode_option"
_KEY_DEEP_MODE_TITLE = "deep_mode_title"
_KEY_MODE_TEXT_BUTTON = "mode_text_button"
_KEY_MODE_POPOVER = "mode_popover"
_KEY_MODE_TITLE = "mode_title"
_KEY_ZD_ICON_TEXT = "zd_icon_text"
_KEY_COIN_BALANCE = "coin_balance"

# ── 创作模式名称（与 radio 按钮索引对应）─────────────────────────────────────
CREATION_MODES = ["精准渲染", "创作渲染", "效果图美化"]

# ── DeepMode 选项名称（仅精准渲染页有）───────────────────────────────────────
DEEP_MODES = ["标准模式", "思考模式", "Nano Banana Pro"]

# ── 创作渲染 / 效果图美化的子模式选项 ────────────────────────────────────────
SUB_MODES_IDEA = ["标准模式", "Nano Banana Pro"]
SUB_MODES_IMAGE = ["标准模式", "Nano Banana Pro"]

# ── 各页面 menuKey ───────────────────────────────────────────────────────────
_MODE_URLS = {
    "精准渲染": "menuKey=precisionRender",
    "创作渲染": "menuKey=ideaRender",
    "效果图美化": "menuKey=imageEnhancement",
}

# ── 完整价格矩阵（7 个组合）──────────────────────────────────────────────────
# (creation_mode_index, creation_mode_name, sub_mode_name, expected_price, url_key)
PRICE_MATRIX = [
    (0, "精准渲染", "标准模式",         6,  "precisionRender"),
    (0, "精准渲染", "思考模式",        12,  "precisionRender"),
    (0, "精准渲染", "Nano Banana Pro", 15,  "precisionRender"),
    (1, "创作渲染", "标准模式",        16,  "ideaRender"),
    (1, "创作渲染", "Nano Banana Pro", 15,  "ideaRender"),
    (2, "效果图美化", "标准模式",       4,  "imageEnhancement"),
    (2, "效果图美化", "Nano Banana Pro", 15, "imageEnhancement"),
]

# ── API 拦截目标 ──────────────────────────────────────────────────────────────
_TARGET_API = "aiDrawPrice"

# ── JS 工具函数 ───────────────────────────────────────────────────────────────
_JS_DISMISS_MODALS = """() => {
    document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
}"""


class PrecisionRenderPricingPage(BasePage):
    """精准渲染定价采集页面操作类（切换创作模式×DeepMode → 采集价格 → 拦截接口）。"""

    DEFAULT_URL = (
        "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=precisionRender"
    )

    def __init__(self, page: Page, auto_close_popups: bool = True) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/precision_render_pricing_elements.yaml",
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
            PopupStrategy(
                name="precision_render_upgrade_modal",
                trigger_selector="[class*='PrecisionRenderUpgradeModal']",
                close_selector=(
                    "[class*='close'], .ant-modal-close, "
                    "[class*='CloseIcon'], [class*='closeIcon']"
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
        """进入精准渲染定价采集页面。

        直接导航到 precisionRender 页，保留 URL 验证和弹窗清理。
        """
        target_url = url or self.DEFAULT_URL

        # 直接导航
        super().goto(target_url, close_popups_after_load=False, wait_state=wait_state)
        self.page.wait_for_timeout(3000)

        # URL 验证
        if "menuKey=precisionRender" not in self.page.url:
            _logger.warning(
                "导航后未到达 precisionRender 页（当前 %s），清理弹窗后重试",
                self.page.url,
            )
            self._dismiss_modals()
            self.page.wait_for_timeout(500)
            self.page.goto(target_url, wait_until=wait_state, timeout=20_000)
            self.page.wait_for_timeout(3000)

            if "menuKey=precisionRender" not in self.page.url:
                raise RuntimeError(
                    f"导航到 precisionRender 页失败，当前 URL: {self.page.url}。"
                    "请检查登录态或弹窗处理。"
                )

        _logger.info("goto 完成，当前 URL: %s", self.page.url)

        # 弹窗清理
        self._dismiss_modals()
        self.page.wait_for_timeout(300)

        # 等待创作模式 radio 可见
        self.get_locator(_KEY_RADIO_ITEM).first.wait_for(
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

    # ===== 弹窗处理 =====

    def _dismiss_modals(self) -> None:
        """通过 JS 移除所有 ant-modal 叠加层。

        用于 PrecisionRenderUpgradeModal 等拦截型弹窗。
        """
        self.page.evaluate(_JS_DISMISS_MODALS)

    # ===== 创作模式切换 =====

    def get_creation_mode_count(self) -> int:
        """返回创作模式 radio 按钮数量。"""
        items = self.get_locator(_KEY_RADIO_ITEM)
        return items.count()

    def get_current_creation_mode_index(self) -> Optional[int]:
        """获取当前选中的创作模式索引（0-based）。

        判断依据：radio 按钮容器 class 含 "selected"
        （实际类名: radioItemSelected）。
        """
        items = self.get_locator(_KEY_RADIO_ITEM)
        count = items.count()
        for i in range(count):
            item = items.nth(i)
            cls = (item.get_attribute("class") or "").lower()
            if "selected" in cls:
                return i
        return None

    def get_creation_mode_name(self, index: int) -> str:
        """获取指定索引创作模式的文本。"""
        items = self.get_locator(_KEY_RADIO_ITEM)
        items.nth(index).wait_for(state="visible", timeout=10_000)
        return items.nth(index).inner_text().strip()

    def switch_creation_mode(self, index: int) -> None:
        """切换到指定索引的创作模式。

        通过 JS dispatchEvent 点击 radio 按钮，绕过升级弹窗的叠加层拦截。
        切换后自动清理弹窗，等待页面重新渲染。

        注意：切换创作模式会导致 SPA 路由变更：
          [0] 精准渲染  → menuKey=precisionRender
          [1] 创作渲染  → menuKey=ideaRender
          [2] 效果图美化 → menuKey=imageEnhancement
        """
        items = self.get_locator(_KEY_RADIO_ITEM)
        target = items.nth(index)
        target.wait_for(state="visible", timeout=5000)

        # 检查是否已选中（class 含 "selected"）
        cls = (target.get_attribute("class") or "").lower()
        if "selected" in cls:
            _logger.info("创作模式 %d 已选中，跳过点击", index)
            return

        # 通过 JS 点击，绕过 ant-modal 叠加层拦截
        self.page.evaluate("""(index) => {
            const radios = document.querySelectorAll('[class*="radioItem"]');
            if (radios.length > index) radios[index].click();
        }""", index)
        self.page.wait_for_timeout(3000)

        # 清理升级弹窗
        self._dismiss_modals()
        self.page.wait_for_timeout(1000)

        # 等待目标页面渲染完毕（radio 按钮重新可见）
        items = self.get_locator(_KEY_RADIO_ITEM)
        items.nth(index).wait_for(state="visible", timeout=10_000)
        _logger.info("已切换到创作模式 %d，当前 URL: %s", index, self.page.url)

    def has_deep_mode(self) -> bool:
        """检查当前页面是否有 DeepMode 选项。

        仅精准渲染页（menuKey=precisionRender）有 DeepMode。
        """
        trigger = self.get_locator(_KEY_DEEP_MODE_TRIGGER)
        return trigger.count() > 0

    # ===== 直接 URL 导航 =====

    def navigate_to_mode(self, menu_key: str) -> None:
        """直接导航到指定 menuKey 页面（不依赖 radio 按钮点击）。

        :param menu_key: URL 参数值（precisionRender / ideaRender / imageEnhancement）
        """
        base = "https://ai.znzmo.cn/community/AIDrawPage.html"
        target_url = f"{base}?menuKey={menu_key}"

        if menu_key in self.page.url:
            _logger.info("已在 %s 页，跳过导航", menu_key)
            return

        self.page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
        self.page.wait_for_timeout(3000)
        self._dismiss_modals()
        self.page.wait_for_timeout(300)

        # 等待创作模式 radio 可见
        self.get_locator(_KEY_RADIO_ITEM).first.wait_for(
            state="visible", timeout=15_000
        )
        _logger.info("navigate_to_mode 完成，当前 URL: %s", self.page.url)

    # ===== 子模式切换（创作渲染 / 效果图美化）=====

    def switch_sub_mode(self, mode_name: str, max_retries: int = 2) -> bool:
        """通过 modeText 按钮切换子模式（用于创作渲染 / 效果图美化）。

        切换后验证价格是否变化（而非仅检查按钮文本），未生效则重试。

        :param mode_name: 目标子模式名称（如 "标准模式" 或 "Nano Banana Pro"）
        :param max_retries: 最大重试次数
        :return: 是否成功切换
        """
        mode_text_btn = self.get_locator(_KEY_MODE_TEXT_BUTTON).first
        try:
            mode_text_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            _logger.warning("modeText 按钮不可见，当前页面可能不支持子模式切换")
            return False

        # 检查是否已是目标模式
        current_text = mode_text_btn.inner_text().strip()
        if self._is_mode_match(mode_name, current_text):
            _logger.info("子模式已是 %s，跳过切换", mode_name)
            return True

        # 记录切换前的价格（用于验证切换是否真正生效）
        price_before = self.get_current_price()

        for attempt in range(max_retries):
            # 用 Playwright 原生点击 modeText 按钮（比 JS click 更可靠地触发事件）
            try:
                mode_text_btn.click()
            except Exception:
                self.page.evaluate("""() => {
                    const btn = document.querySelector('[class*="modeText"]');
                    if (btn) btn.click();
                }""")
            self.page.wait_for_timeout(800)

            # 在 popover 中找到匹配的选项并点击
            # 优先用 Playwright 原生 click（触发完整事件链）
            clicked = False
            panel = self.page.locator('[class*="modeTextPopover"], [class*="popover"], [class*="dropdown"]')
            if panel.count() > 0:
                options = panel.first.locator('[class*="mode__"]')
                for i in range(options.count()):
                    opt = options.nth(i)
                    try:
                        title = opt.locator('[class*="modeTitle"]')
                        if title.count() > 0 and mode_name in title.first.inner_text():
                            opt.scroll_into_view_if_needed()
                            opt.click()
                            clicked = True
                            break
                    except Exception:
                        continue
            # 兜底：JS click
            if not clicked:
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
                _logger.warning("未找到子模式选项: %s", mode_name)
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)
                return False

            self.page.wait_for_timeout(2000)
            self._dismiss_modals()
            self.page.wait_for_timeout(500)

            # 验证：检查价格是否变化（最可靠的信号）
            price_after = self.get_current_price()
            if price_after and price_after != price_before:
                _logger.info(
                    "子模式切换验证通过（价格变化）: %s → %s, 价格 %s → %s",
                    mode_name, mode_text_btn.inner_text().strip(),
                    price_before, price_after,
                )
                return True

            # 备选验证：按钮文本匹配
            try:
                new_text = mode_text_btn.inner_text().strip()
            except Exception:
                new_text = ""
            if self._is_mode_match(mode_name, new_text):
                _logger.info("子模式切换验证通过（按钮文本）: %s → %s", mode_name, new_text)
                return True

            _logger.warning(
                "子模式切换 attempt %d 未生效: 价格 %s→%s, 按钮 '%s'",
                attempt + 1, price_before, price_after, new_text,
            )

        _logger.error("子模式切换到 '%s' 失败，已重试 %d 次", mode_name, max_retries)
        return False

    @staticmethod
    def _is_mode_match(mode_name: str, text: str) -> bool:
        """判断 text 是否表示已选中 mode_name。

        处理页面显示文本截断的情况，如：
        - "Nano Banana Pro" vs 按钮显示 "Banana Pro"（省略前缀）
        - "标准模式" vs 按钮显示 "标准"（省略"模式"）
        """
        if not text:
            return False
        if mode_name in text:
            return True
        # 按钮可能截断前缀："Nano Banana Pro" → "Banana Pro"
        if "Banana Pro" in mode_name and "Banana Pro" in text:
            return True
        # 标准模式：按钮可能显示 "标准" 而非完整 "标准模式"
        if mode_name == "标准模式" and "标准" in text:
            return True
        return False

    # ===== DeepMode 切换（仅精准渲染页）=====

    def _open_deep_mode_panel(self) -> None:
        """通过 JS 点击 DeepMode 触发器展开面板。"""
        self.page.evaluate("""() => {
            const trigger = document.querySelector('[class*="deepModeWrapperContainer"]');
            if (trigger) trigger.click();
        }""")
        self.page.wait_for_timeout(1000)

    def _close_deep_mode_panel(self) -> None:
        """关闭 DeepMode 面板（Escape 键）。"""
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def get_current_deep_mode_name(self) -> str:
        """获取当前选中的 DeepMode 名称（从触发器文本读取）。"""
        trigger = self.get_locator(_KEY_DEEP_MODE_TRIGGER).first
        try:
            trigger.wait_for(state="visible", timeout=5000)
            return trigger.inner_text().strip()
        except Exception:
            return ""

    def switch_deep_mode(self, index: int) -> None:
        """切换到指定索引的 DeepMode（仅精准渲染页）。

        通过 JS dispatchEvent 点击选项，绕过升级弹窗的叠加层拦截。
        点击后自动清理弹窗，等待价格刷新。
        """
        # 打开面板
        self._open_deep_mode_panel()

        # 通过 JS 点击选项
        self.page.evaluate("""(index) => {
            const panel = document.querySelector('[class*="aiDrawTooltip"]');
            if (!panel) return;
            const options = panel.querySelectorAll('[class*="mode__"]');
            if (options.length > index) options[index].click();
        }""", index)
        self.page.wait_for_timeout(1500)

        # 清理可能出现的升级弹窗
        self._dismiss_modals()
        self.page.wait_for_timeout(500)

        _logger.info("已切换到 DeepMode %d", index)

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

    # ===== 价格快照 =====

    def _collect_price_snapshot(self, api_count_before: int) -> Dict[str, Any]:
        """采集当前价格、余额，并关联 API 拦截数据。

        :param api_count_before: 调用前已拦截的 API 数量
        :return: {"price_text", "price_value", "coin_balance", "api_response"}
        """
        price_text = self.get_current_price()
        price_value = parse_price(price_text)

        balance = self.get_coin_balance()

        new_api = self._api_captured[api_count_before:]
        api_data = None
        if new_api:
            resp = new_api[-1].get("response_body")
            if resp and isinstance(resp, dict):
                api_data = resp.get("data")

        return {
            "price_text": price_text,
            "price_value": price_value,
            "coin_balance": balance,
            "api_response": api_data,
        }

    # ===== 组合采集 =====

    def capture_combination_price(
        self,
        creation_mode_index: int,
        deep_mode_index: int,
        sub_mode_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """切换到指定创作模式×子模式 组合并采集完整价格信息。

        :param creation_mode_index: 创作模式索引（0=精准渲染, 1=创作渲染, 2=效果图美化）
        :param deep_mode_index: DeepMode 索引（仅精准渲染页有效: 0=标准, 1=思考, 2=Nano）；-1=无
        :param sub_mode_name: 子模式名称（创作渲染/效果图美化用，如 "标准模式"、"Nano Banana Pro"）
        :return: 价格信息字典
        """
        # 切换创作模式
        self.switch_creation_mode(creation_mode_index)
        creation_mode_name = self.get_creation_mode_name(creation_mode_index)

        # 记录 API 拦截数
        api_count_before = len(self._api_captured)

        # 根据页面类型切换子模式
        deep_mode_name = "无"
        if self.has_deep_mode():
            # 精准渲染页：使用 DeepMode 面板
            if deep_mode_index >= 0:
                self.switch_deep_mode(deep_mode_index)
                deep_mode_name = self.get_current_deep_mode_name()
        elif sub_mode_name:
            # 创作渲染/效果图美化：使用 modeText popover
            self.switch_sub_mode(sub_mode_name)
            deep_mode_name = sub_mode_name

        # 采集价格、余额、API 响应
        snapshot = self._collect_price_snapshot(api_count_before)

        return {
            "creation_mode_index": creation_mode_index,
            "creation_mode": creation_mode_name,
            "deep_mode_index": deep_mode_index,
            "deep_mode": deep_mode_name,
            "sub_mode": deep_mode_name,
            **snapshot,
            "capture_time": datetime.now().isoformat(),
        }

    def capture_all_combinations(self) -> List[Dict[str, Any]]:
        """遍历所有创作模式×子模式组合（共 7 个），逐个切换并采集价格。

        策略：
        - 精准渲染 (precisionRender)：3 种 DeepMode → 3 组合
        - 创作渲染 (ideaRender)：2 种子模式（标准模式 / Nano Banana Pro）→ 2 组合
        - 效果图美化 (imageEnhancement)：2 种子模式（标准模式 / Nano Banana Pro）→ 2 组合
        共 7 组合。

        :return: 每个组合的价格信息列表
        """
        results = []

        # ── 精准渲染：直接导航 + DeepMode 面板切换 ──
        _logger.info("=== 采集精准渲染 ===")
        self.navigate_to_mode("precisionRender")

        for di in range(len(DEEP_MODES)):
            api_count_before = len(self._api_captured)

            self.switch_creation_mode(0)
            self.switch_deep_mode(di)
            deep_mode_name = self.get_current_deep_mode_name()

            snapshot = self._collect_price_snapshot(api_count_before)

            results.append({
                "creation_mode_index": 0,
                "creation_mode": "精准渲染",
                "deep_mode_index": di,
                "deep_mode": deep_mode_name,
                "sub_mode": deep_mode_name,
                **snapshot,
                "capture_time": datetime.now().isoformat(),
            })
            _logger.info("采集 精准渲染 × %s = %s 知点", deep_mode_name, snapshot["price_text"])

        # ── 创作渲染：直接导航 + modeText popover 子模式切换 ──
        _logger.info("=== 采集创作渲染 ===")
        self.navigate_to_mode("ideaRender")

        for sm in SUB_MODES_IDEA:
            api_count_before = len(self._api_captured)

            self.switch_sub_mode(sm)

            snapshot = self._collect_price_snapshot(api_count_before)

            results.append({
                "creation_mode_index": 1,
                "creation_mode": "创作渲染",
                "deep_mode_index": -1,
                "deep_mode": sm,
                "sub_mode": sm,
                **snapshot,
                "capture_time": datetime.now().isoformat(),
            })
            _logger.info("采集 创作渲染 × %s = %s 知点", sm, snapshot["price_text"])

        # ── 效果图美化：直接导航 + modeText popover 子模式切换 ──
        _logger.info("=== 采集效果图美化 ===")
        self.navigate_to_mode("imageEnhancement")

        for sm in SUB_MODES_IMAGE:
            api_count_before = len(self._api_captured)

            self.switch_sub_mode(sm)

            snapshot = self._collect_price_snapshot(api_count_before)

            results.append({
                "creation_mode_index": 2,
                "creation_mode": "效果图美化",
                "deep_mode_index": -1,
                "deep_mode": sm,
                "sub_mode": sm,
                **snapshot,
                "capture_time": datetime.now().isoformat(),
            })
            _logger.info("采集 效果图美化 × %s = %s 知点", sm, snapshot["price_text"])

        return results
