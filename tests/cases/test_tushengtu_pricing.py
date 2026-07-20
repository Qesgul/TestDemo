# -*- coding: utf-8 -*-
"""旧版图生图定价采集 - 测试用例

覆盖 家装(6) + 建筑(5) = 11 个子分类的价格采集。

运行：
  pytest tests/cases/test_tushengtu_pricing.py -v
"""
import pytest

from common.pricing_helpers import api_login, inject_cookie
from pages.methods.tushengtu_pricing_page import TushengtuPricingPage, CATEGORY_SUBS

# 强制定价测试在同一 worker 串行执行，避免多设备登录被踢
pytestmark = pytest.mark.xdist_group("pricing")

_MEMBER = "新钻石会员"

# 预期价格（新钻石会员）
EXPECTED_PRICES = {
    ("家装", "创作渲染"): 16,
    ("家装", "精准渲染"): 6,
    ("家装", "平面填彩"): 8,
    ("家装", "毛坯精装设计"): 8,
    ("家装", "新房软装搭配"): 8,
    ("家装", "旧房改造焕新"): 8,
    ("建筑", "创作渲染"): 8,
    ("建筑", "精准渲染"): 16,
    ("建筑", "总平填彩"): 16,
    ("建筑", "实景改造"): 16,
    ("建筑", "环境生成器"): 4,
}

# ── class 级 fixture ──────────────────────────────────────────────────────────
@pytest.fixture(scope="class")
def pricing_session(browser):
    """Class 级登录 fixture。"""
    context = browser.new_context()
    page = context.new_page()
    token = api_login(_MEMBER)
    inject_cookie(page, token)
    yield page, token
    page.close()
    context.close()


# ── 测试类 ───────────────────────────────────────────────────────────────────
class TestTushengtuPricing:
    """旧版图生图 UI 定价采集。"""

    @pytest.mark.core
    def test_capture_all(self, pricing_session, assertion):
        """遍历家装(6)+建筑(5)共 11 个子分类，采集价格并校验。"""
        page, _ = pricing_session

        pricing_page = TushengtuPricingPage(page, auto_close_popups=False)
        pricing_page.goto()

        results = pricing_page.capture_all()

        # 校验总数
        total_expected = sum(len(v) for v in CATEGORY_SUBS.values())
        assertion.assert_equal(
            len(results),
            total_expected,
            name="total_subcategories",
            message=f"应有 {total_expected} 个子分类，实际: {len(results)}",
        )

        # 校验每个组合
        for r in results:
            key = (r["category"], r["subcategory"])
            combo_label = f"{r['category']}/{r['subcategory']}"

            # 价格非空
            assertion.assert_true(
                r["price_text"] != "",
                name=f"{combo_label}_price_not_empty",
                message=f"{combo_label} 价格不应为空",
            )

            # 价格为正整数
            if r["price_value"] is not None:
                assertion.assert_true(
                    r["price_value"] > 0,
                    name=f"{combo_label}_price_positive",
                    message=f"{combo_label} 价格应为正整数，实际: {r['price_value']}",
                )

            # 预期价格校验
            expected = EXPECTED_PRICES.get(key)
            if expected is not None:
                assertion.assert_equal(
                    r["price_value"],
                    expected,
                    name=f"{combo_label}_price_expected",
                    message=f"{combo_label} 预期 {expected}，实际 {r['price_value']}",
                )

        # 打印汇总
        lines = ["\n" + "=" * 60, "旧版图生图定价采集汇总", "=" * 60]
        for r in results:
            lines.append(
                f"  {r['category']:<6} {r['subcategory']:<16} {r['price_text']:<8}"
            )
        lines.append("=" * 60)
        print("\n".join(lines))
