# -*- coding: utf-8 -*-
"""更多 AI 绘图产品定价采集 - 平面填彩 / 实景改造 / 全景渲染

覆盖 7 个价格组合（新钻石会员）：
  平面填彩:   标准模式=8|16(不稳定), Nano Banana Pro=15,  GPT Image 2=15
  实景改造:   标准模式=16, Nano Banana Pro=15
  全景渲染:   标准模式=4,  Nano Banana Pro=15

运行：
  pytest tests/cases/test_more_ai_pricing.py --override-ini="addopts=-q -s --headed" -v
"""

import pytest

from common.pricing import get_expected_price
from common.pricing_helpers import api_login, inject_cookie, dismiss_modals, parse_price

# 强制定价测试在同一 worker 串行执行，避免多设备登录被踢
pytestmark = pytest.mark.xdist_group("pricing")

_MEMBER = "新钻石会员"

# ── 常量 ──────────────────────────────────────────────────────────────────────
_BASE_URL = "https://ai.znzmo.cn/community/AIDrawPage.html"

# ── 模式切换辅助 ──────────────────────────────────────────────────────────────

def _switch_mode(page, mode_name: str, max_retries: int = 2) -> None:
    """通过 modeText + modeTitle 切换子模式。"""
    for _ in range(max_retries):
        mode_btn = page.locator('[class*="modeText"]').first
        if mode_name in mode_btn.text_content().strip():
            return
        page.evaluate('el => el.click()', mode_btn.element_handle())
        page.wait_for_timeout(1200)
        page.evaluate("""(modeName) => {
            const titles = document.querySelectorAll('[class*="modeTitle"]');
            for (const t of titles) {
                if (t.textContent.trim().includes(modeName)) {
                    (t.closest('[class*="mode__"]') || t.parentElement || t).click();
                    return true;
                }
            }
            return false;
        }""", mode_name)
        page.wait_for_timeout(2000)
        dismiss_modals(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        if mode_name in mode_btn.text_content().strip():
            return


def _switch_deep_mode(page, mode_name: str, max_retries: int = 2) -> None:
    """通过 deepModeWrapperContainer 切换 DeepMode。"""
    for _ in range(max_retries):
        deep = page.locator('[class*="deepModeWrapperContainer"]').first
        if not deep.is_visible(timeout=3000):
            return
        if mode_name in deep.text_content().strip():
            return
        page.evaluate('el => el.click()', deep.element_handle())
        page.wait_for_timeout(1200)
        page.evaluate("""(modeName) => {
            const titles = document.querySelectorAll('[class*="modeTitle"]');
            for (const t of titles) {
                if (t.textContent.trim().includes(modeName)) {
                    (t.closest('[class*="mode__"]') || t.parentElement || t).click();
                    return true;
                }
            }
            return false;
        }""", mode_name)
        page.wait_for_timeout(2000)
        dismiss_modals(page)
        if mode_name in deep.text_content().strip():
            return


def _capture_price(page):
    """采集价格。"""
    price_el = page.locator('[class*="zdIconText"]').first
    price_el.wait_for(state="visible", timeout=10_000)
    text = price_el.text_content().strip()
    return parse_price(text), text


# ── class 级 fixture：每个测试类共享一次登录 ──────────────────────────────────

@pytest.fixture(scope="class")
def pricing_session(request, browser):
    """Class 级登录 fixture：独立 context/page，不干扰 pytest-playwright 的 page。

    扩展多账号时：@pytest.fixture(params=["新钻石会员", "铂金会员"])
    """
    member = getattr(request, "param", _MEMBER)
    context = browser.new_context()
    page = context.new_page()
    token = api_login(member)
    inject_cookie(page, token)
    yield page, token
    page.close()
    context.close()


# ── 测试类：平面填彩（1次登录，遍历3个模式）────────────────────────────────

class TestFloorPlanColor:
    """平面填彩定价采集。"""

    @pytest.mark.core
    def test_all_modes(self, pricing_session, assertion):
        page, _ = pricing_session
        page.goto(f"{_BASE_URL}?menuKey=floorPlanColor", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        dismiss_modals(page)

        modes = [
            # (模式名, 预期价格, 是否精确校验)
            # 标准模式价格受批次大小影响不稳定（8或16），只校验正整数
            ("标准模式",       None, False),
            ("Nano Banana Pro", 15,   True),
            ("GPT Image 2",    15,   True),
        ]
        for mode_name, expected, exact in modes:
            _switch_mode(page, mode_name)
            price_value, price_text = _capture_price(page)

            baseline = get_expected_price("平面填彩", mode_name, _MEMBER)
            if exact and baseline is not None:
                assertion.assert_equal(price_value, baseline,
                    name=f"flat_{mode_name}_baseline")
            if exact and expected is not None:
                assertion.assert_equal(price_value, expected,
                    name=f"flat_{mode_name}_expected")
            else:
                assertion.assert_true(
                    isinstance(price_value, int) and price_value > 0,
                    name=f"flat_{mode_name}_positive",
                    message=f"平面填彩×{mode_name} 价格应为正整数，实际: {price_value}",
                )

        # 打印汇总
        print(f"\n  平面填彩: {[m[0] for m in modes]} ✓")


# ── 测试类：实景改造（1次登录，遍历2个模式）────────────────────────────────

class TestInsituRenovation:
    """实景改造定价采集。"""

    @pytest.mark.core
    def test_all_modes(self, pricing_session, assertion):
        page, _ = pricing_session
        page.goto(f"{_BASE_URL}?menuKey=insituRenovation", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        dismiss_modals(page)

        modes = [
            ("标准模式",       16),
            ("Nano Banana Pro", 15),
        ]
        for mode_name, expected in modes:
            _switch_mode(page, mode_name)
            price_value, price_text = _capture_price(page)

            baseline = get_expected_price("实景改造", mode_name, _MEMBER)
            if baseline is not None:
                assertion.assert_equal(price_value, baseline,
                    name=f"renovation_{mode_name}_baseline")
            assertion.assert_equal(price_value, expected,
                name=f"renovation_{mode_name}_expected")

        print(f"\n  实景改造: {[m[0] for m in modes]} ✓")


# ── 测试类：全景渲染（1次登录，遍历2个模式，侧边栏进入）────────────────────

class TestPanoramicRender:
    """全景渲染定价采集（侧边栏进入）。"""

    @pytest.mark.core
    def test_all_modes(self, pricing_session, assertion):
        page, _ = pricing_session

        # 侧边栏进入（直接 goto 会被重定向）
        page.goto(f"{_BASE_URL}?menuKey=home", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        dismiss_modals(page)
        page.locator("text=全景渲染").first.click()
        page.wait_for_timeout(5000)
        dismiss_modals(page)

        modes = [
            ("标准模式",       4),
            ("Nano Banana Pro", 15),
        ]
        for mode_name, expected in modes:
            _switch_deep_mode(page, mode_name)
            price_value, price_text = _capture_price(page)

            baseline = get_expected_price("全景渲染", mode_name, _MEMBER)
            if baseline is not None:
                assertion.assert_equal(price_value, baseline,
                    name=f"panoramic_{mode_name}_baseline")
            assertion.assert_equal(price_value, expected,
                name=f"panoramic_{mode_name}_expected")

        print(f"\n  全景渲染: {[m[0] for m in modes]} ✓")
