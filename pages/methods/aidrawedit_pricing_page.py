# -*- coding: utf-8 -*-
"""AIDrawEdit 定价采集 Page Object。

页面 URL: https://ai.znzmo.cn/AIDrawEdit?domain={0|1|3|4}
- domain=0: 通用设计   domain=1: 室内设计
- domain=3: 建筑设计   domain=4: 景观设计
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from common.pricing_helpers import dismiss_modals, parse_price

_logger = logging.getLogger(__name__)

_BASE_URL = "https://ai.znzmo.cn/AIDrawEdit"
_IMG_PATH = str(Path(__file__).resolve().parent.parent / "file" / "testImg.jpg")

DOMAINS = {0: "通用设计", 1: "室内设计", 3: "建筑设计", 4: "景观设计"}


class AIDrawEditPricingPage:
    """AIDrawEdit 定价采集页面对象。"""

    def __init__(self, page: Page, *, auto_close_popups: bool = True):
        self.page = page
        self._auto_close = auto_close_popups
        self._api_captured: List[Dict[str, Any]] = []

    # ===== 等待辅助 =====

    def _wait_for_scenes_ready(self, timeout: int = 10_000) -> None:
        """等待场景列表渲染完成。"""
        try:
            self.page.wait_for_selector(
                '[class*="menuItem"] [class*="menuName"]', timeout=timeout
            )
        except Exception:
            self.page.wait_for_timeout(1000)

    # ===== 导航 =====

    def goto(self, domain: int = 0) -> None:
        self.page.goto(f"{_BASE_URL}?domain={domain}", wait_until="domcontentloaded", timeout=30_000)
        self.page.wait_for_timeout(6000)
        if self._auto_close:
            dismiss_modals(self.page)

    # ===== API 拦截 =====

    def enable_api_intercept(self) -> None:
        if hasattr(self, '_intercepted') and self._intercepted:
            return
        def _on_route(route):
            req = route.request
            resp = route.fetch()
            try:
                body = resp.json()
            except Exception:
                body = None
            entry = {"url": req.url, "request_body": None, "response_body": body}
            pd = req.post_data
            if pd:
                try:
                    import json
                    entry["request_body"] = json.loads(pd)
                except Exception:
                    entry["request_body"] = pd
            self._api_captured.append(entry)
            route.fulfill(response=resp)
        self.page.route("**/aiDrawPrice**", _on_route)
        self._intercepted = True

    @property
    def api_captured(self) -> List[Dict[str, Any]]:
        return list(self._api_captured)

    # ===== 图片上传 =====

    def upload_image(self, img_path: Optional[str] = None) -> None:
        file_input = self.page.locator('input[type="file"]')
        file_input.first.wait_for(state="attached", timeout=30000)
        file_input.first.set_input_files(img_path or _IMG_PATH)
        self.page.wait_for_timeout(6000)
        if self._auto_close:
            dismiss_modals(self.page)

    # ===== 领域切换 =====

    def switch_domain(self, domain: int) -> None:
        """通过 URL 参数切换领域（domain 直接对应 ?domain= 参数）。"""
        name = DOMAINS.get(domain, "")
        if not name:
            raise ValueError(f"未知领域: {domain}")

        self.page.goto(f"{_BASE_URL}?domain={domain}", wait_until="domcontentloaded", timeout=30_000)
        self.page.wait_for_timeout(2000)
        if self._auto_close:
            dismiss_modals(self.page)

    def switch_domain_via_selector(self, domain: int) -> None:
        """通过页面左上角领域选择器切换领域（SPA 内切换，不触发页面重载）。

        用于上传图片后切换领域——上传会导致 URL 跳回默认领域，
        用 URL 导航会丢失已上传的图片，所以必须用 UI 选择器。
        """
        name = DOMAINS.get(domain, "")
        if not name:
            raise ValueError(f"未知领域: {domain}")

        # 点击领域选择器打开下拉（ant-dropdown-trigger 含 customSelect）
        selector = self.page.locator(
            '[class*="customSelect"][class*="simpleFieldSelect"],'
            '[class*="customSelect"][class*="simpleFieldSele"]'
        ).first
        selector.click(timeout=5000)
        self.page.wait_for_timeout(500)

        # 在下拉选项中点击目标领域
        option = self.page.locator(
            f'[class*="scaleItem"]:has-text("{name}")'
        ).first
        option.click(timeout=3000)
        self.page.wait_for_timeout(2000)

        if self._auto_close:
            dismiss_modals(self.page)

    # ===== 获取全部场景 =====

    def get_all_scenes(self) -> Dict[str, List[str]]:
        """获取当前领域下全部场景：顶部可见 + 更多弹窗。"""
        # 确保弹窗不阻塞交互
        dismiss_modals(self.page)

        visible = []
        menu_items = self.page.locator('[class*="menuItem"] [class*="menuName"]')
        for i in range(menu_items.count()):
            text = menu_items.nth(i).inner_text().strip()
            if text and text != "更多":
                visible.append(text)

        more = []
        trigger = self.page.locator('[class*="moreMenuTrigger"]')
        if trigger.count() > 0 and trigger.first.is_visible():
            trigger.first.click()
            self.page.wait_for_timeout(800)
            popup_items = self.page.locator('[class*="moreMenuDropdown"] li')
            for i in range(popup_items.count()):
                more.append(popup_items.nth(i).inner_text().strip())
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)

        return {"visible": visible, "more": more}

    # ===== 场景选择（安全版） =====

    def select_scene_safe(self, scene_name: str) -> bool:
        """尝试选中指定场景（先顶栏，再多弹窗）。"""
        # 顶栏
        target = self.page.locator(f'[class*="menuItem"]:has-text("{scene_name}")').first
        if target.is_visible(timeout=1000):
            target.click()
            self.page.wait_for_timeout(1000)
            if self._auto_close:
                dismiss_modals(self.page)
            cls = target.get_attribute("class") or ""
            if "active" in cls.lower():
                return True
            _logger.info("场景 '%s' 点击后未激活，跳过", scene_name)
            return False

        # 更多弹窗
        trigger = self.page.locator('[class*="moreMenuTrigger"]')
        if trigger.count() > 0 and trigger.first.is_visible(timeout=1000):
            trigger.first.click()
            self.page.wait_for_timeout(800)
            item = self.page.locator(f'[class*="moreMenuDropdown"] li:has-text("{scene_name}")')
            if item.count() > 0 and item.first.is_visible(timeout=1000):
                item.first.click()
                self.page.wait_for_timeout(1000)
                if self._auto_close:
                    dismiss_modals(self.page)
                top = self.page.locator(f'[class*="menuItem"]:has-text("{scene_name}")').first
                if top.is_visible(timeout=2000):
                    top_cls = top.get_attribute("class") or ""
                    if "active" in top_cls.lower():
                        return True
                _logger.info("场景 '%s'(更多) 点击后未激活，跳过", scene_name)
                return False
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)

        return False

    # ===== 选区清除 =====

    def clear_selection(self) -> None:
        """清除当前选区状态（退出编辑模式）。

        上传图片后页面可能自动进入智能选择，需要清除以确保非编辑模式采集准确。
        按 Escape 关闭选区 UI，再按一次确保完全退出。
        """
        for _ in range(3):
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        # 如果仍有选区遮罩，点击页面顶部非 canvas 区域
        if self._is_selection_mask_visible():
            try:
                self.page.mouse.click(10, 10)
                self.page.wait_for_timeout(500)
            except Exception:
                pass

    # ===== 涂抹 =====

    def paint_on_canvas(self, distance: int = 300) -> None:
        """B 键激活涂抹 → A→B 直线拖拽。"""
        self.page.keyboard.press("b")
        self.page.wait_for_timeout(500)
        canvas = self.page.locator("canvas").first
        if not canvas.is_visible(timeout=5000):
            return
        box = canvas.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(cx, cy)
        self.page.mouse.down()
        self.page.mouse.move(cx + distance, cy, steps=20)
        self.page.mouse.up()
        self.page.wait_for_timeout(1500)

    def has_selection_mask(self) -> bool:
        mask = self.page.locator('[class*="SelectionMask"]')
        return mask.count() > 0 and mask.first.is_visible()

    # ===== 模型切换 =====

    def _is_selection_mask_visible(self) -> bool:
        """检测"请先在底图上绘制选区"遮罩是否可见。"""
        mask = self.page.locator('[class*="SelectionMaskContainer"]')
        return mask.count() > 0 and mask.first.is_visible(timeout=300)

    def get_model_options(self) -> List[str]:
        """获取所有可选模型名称。若无模型选择器或按钮disabled返回空列表。"""
        btn = self.page.locator('[class*="modeSelectBtn"]')
        if btn.count() == 0:
            return []
        # 检查按钮是否disabled（如通用设计的高清放大/细节增强/去水印/修复人物）
        cls = btn.first.get_attribute("class") or ""
        if "disabled" in cls.lower():
            return []
        # 遮罩可见说明当前模式不可用，直接返回空列表跳过
        if self._is_selection_mask_visible():
            return []
        btn.first.click(timeout=3000)
        self.page.wait_for_timeout(800)
        names = self.page.evaluate("""() => {
            const items = document.querySelectorAll('[class*="ModeSelectList__mode__"]');
            return Array.from(items).map(el => {
                const t = el.querySelector('[class*="modeTitle"]');
                return t ? t.innerText.trim() : '';
            }).filter(n => n);
        }""")
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        return names

    def switch_model(self, model_name: str) -> bool:
        """切换到指定模型。"""
        btn = self.page.locator('[class*="modeSelectBtn"]')
        if btn.count() == 0:
            return False

        # 遮罩可见说明当前模式不可用，直接返回
        if self._is_selection_mask_visible():
            return False

        # 关闭可能存在的 tooltip（如"换视角"场景的"请填写视角描述"）
        # 点击页面顶部空白区域转移焦点，避免点击 canvas 触发智能选择
        try:
            header = self.page.locator('header, [class*="header"], [class*="topBar"], [class*="nav"]').first
            if header.is_visible(timeout=500):
                box = header.bounding_box()
                self.page.mouse.click(box["x"] + 5, box["y"] + box["height"] + 20)
            else:
                # fallback: 点击页面左上角非 canvas 区域
                self.page.mouse.click(10, 10)
            self.page.wait_for_timeout(200)
        except Exception:
            pass

        # 点击模型选择按钮
        try:
            btn.first.click(timeout=2000, force=True)
        except Exception:
            btn.first.click(timeout=2000)
        self.page.wait_for_timeout(800)

        # 查找目标模型
        target = self.page.locator(f'[class*="modeTitle"]:has-text("{model_name}")').first
        if not target.is_visible(timeout=1500):
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(200)
            return False

        # 点击目标模型
        target.click()
        self.page.wait_for_timeout(800)

        # 验证切换成功
        current = self.get_current_model()
        return model_name in current

    def get_current_model(self) -> str:
        try:
            return self.page.locator('[class*="modeSelectBtn"]').first.inner_text().strip()
        except Exception:
            return ""

    def get_current_price(self) -> str:
        """获取当前价格文本。"""
        el = self.page.locator('[class*="zdIconText"]').first
        try:
            el.wait_for(state="visible", timeout=3000)
            return el.inner_text().strip()
        except Exception:
            pass

        gen_btn = self.page.locator('[class*="genBtn"]').first
        try:
            gen_btn.wait_for(state="visible", timeout=3000)
            text = gen_btn.inner_text().strip()
            m = re.match(r"(\d+)\s*生成", text)
            if m:
                return m.group(1)
        except Exception:
            pass

        return ""

    # ===== 批量采集 =====

    def capture_scene_all_models(self, scene_name: str, mode: str) -> List[Dict[str, Any]]:
        """采集当前场景下所有模型的价格 + API 请求。"""
        # 遮罩可见说明当前模式不可用，直接跳过（不读取可能无意义的价格）
        if self._is_selection_mask_visible():
            return []
        models = self.get_model_options()
        _logger.info("场景=%s 模式=%s 模型列表=%s", scene_name, mode, models)

        if not models:
            price_text = self.get_current_price()
            price_value = parse_price(price_text)
            api_data = None
            api_params = None
            if self._api_captured:
                last = self._api_captured[-1]
                resp = last.get("response_body") or {}
                api_data = (resp.get("data") or {}) if isinstance(resp, dict) else None
                api_params = last.get("request_body")
            return [{
                "scene": scene_name, "mode": mode, "model": "固定",
                "price_text": price_text, "price_value": price_value,
                "api_amount": api_data.get("amount") if api_data else None,
                "api_params": api_params,
            }]

        results = []
        for model_name in models:
            self.switch_model(model_name)
            self.page.wait_for_timeout(500)

            price_text = self.get_current_price()
            price_value = parse_price(price_text)

            api_data = None
            api_params = None
            if self._api_captured:
                last = self._api_captured[-1]
                resp = last.get("response_body") or {}
                api_data = (resp.get("data") or {}) if isinstance(resp, dict) else None
                api_params = last.get("request_body")

            results.append({
                "scene": scene_name,
                "mode": mode,
                "model": model_name,
                "price_text": price_text,
                "price_value": price_value,
                "api_amount": api_data.get("amount") if api_data else None,
                "api_params": api_params,
            })
        return results
