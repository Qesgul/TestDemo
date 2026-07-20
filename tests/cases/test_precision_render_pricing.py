# -*- coding: utf-8 -*-
"""精准渲染定价采集 - 自动化测试套件

覆盖范围：
  UI-PR-001~007  7 种创作模式×子模式的 UI 价格采集
  API-PR-001~007 7 种 aiDrawPrice 接口价格查询
  PR-ALL         全组合遍历 + API 拦截数据输出

完整价格矩阵（7 组合）：
  精准渲染 (menuKey=precisionRender)  → DeepMode 面板切换（标准/思考/Nano）
  创作渲染 (menuKey=ideaRender)       → modeText popover 子模式切换（标准/Nano）
  效果图美化 (menuKey=imageEnhancement) → modeText popover 子模式切换（标准/Nano）

登录策略：
  UI 测试：class 级 fixture 单次登录，类内所有测试复用同一个 page
  API 测试：每个测试方法自行 API 登录（不涉及浏览器）

运行方式：
  pytest tests/cases/test_precision_render_pricing.py -k "test_all_combinations_capture" \\
    --override-ini="addopts=-q -s --headed" -v
"""

from datetime import datetime

import pytest

from common.pricing import get_expected_price
from common.pricing_helpers import api_login, inject_cookie, fetch_price, save_result
from common.yaml_loader import load_yaml
from data_types.precision_render_pricing_data_types import APIPricingCase, UIPricingCase
from pages.methods.precision_render_pricing_page import PrecisionRenderPricingPage

# 强制定价测试在同一 worker 串行执行，避免多设备登录被踢
pytestmark = pytest.mark.xdist_group("pricing")

# ── 数据加载 ──────────────────────────────────────────────────────────────────
_DATA_PATH = "tests/data/precision_render_pricing_data.yaml"
_DATA = load_yaml(_DATA_PATH)

_UI_CASES = [UIPricingCase(**c) for c in (_DATA.get("ui_cases") or [])]
_API_CASES = [APIPricingCase(**c) for c in (_DATA.get("api_cases") or [])]

if not _UI_CASES and not _API_CASES:
    pytest.skip("precision_render_pricing_data.yaml 中无用例数据", allow_module_level=True)

_UI_IDS = [c.case_id for c in _UI_CASES]
_API_IDS = [c.case_id for c in _API_CASES]

# ── class 级 fixture：UI 测试类共享一次登录 ─────────────────────────────────
@pytest.fixture(scope="class")
def pricing_session(request, browser):
    """Class 级登录 fixture：独立 context/page，不干扰 pytest-playwright 的 page。"""
    context = browser.new_context()
    page = context.new_page()
    token = api_login()
    inject_cookie(page, token)
    yield page, token
    page.close()
    context.close()


# ── UI 测试类 ─────────────────────────────────────────────────────────────────
class TestUIPrecisionRenderPricing:
    """UI 创作模式×DeepMode 价格采集测试（class 级单次登录）。"""

    @pytest.mark.core
    def test_all_combinations_capture(self, pricing_session, assertion):
        """遍历所有创作模式×子模式（共 7 个组合），采集 UI 价格并输出汇总。"""
        page, token = pricing_session

        # 3. 导航并采集
        pricing_page = PrecisionRenderPricingPage(page, auto_close_popups=False)
        pricing_page.goto()
        pricing_page.enable_api_intercept()

        # 4. 验证创作模式数量
        mode_count = pricing_page.get_creation_mode_count()
        assertion.assert_true(
            mode_count >= 3,
            name="creation_mode_count_at_least_3",
            message=f"至少应有 3 个创作模式，实际: {mode_count}",
        )

        # 5. 遍历采集（7 个组合）
        results = pricing_page.capture_all_combinations()

        # 校验组合总数
        assertion.assert_equal(
            len(results),
            7,
            name="total_combinations_count",
            message=f"应有 7 个组合，实际: {len(results)}",
        )

        # 校验每个组合的价格非空
        for r in results:
            combo_label = f"{r['creation_mode']}×{r.get('sub_mode', r['deep_mode'])}"
            assertion.assert_true(
                r["price_text"] != "",
                name=f"PR-ALL-{r['creation_mode_index']}-{r.get('deep_mode_index', -1)}_price_not_empty",
                message=f"{combo_label} 价格不应为空",
            )

        # 校验完整价格矩阵（从 baseline 统一数据源获取预期值）
        for r in results:
            mode = r["creation_mode"]
            sub = r.get("sub_mode", r["deep_mode"])
            expected = get_expected_price(mode, sub, "新钻石会员")
            if expected is not None:
                assertion.assert_equal(
                    r["price_value"],
                    expected,
                    name=f"PR-KNOWN-{mode}-{sub}_price",
                    message=f"{mode}×{sub} 预期 {expected}，实际 {r['price_value']}",
                )

        # 6. 保存结果
        output = {
            "capture_time": datetime.now().isoformat(),
            "source": "ui",
            "page_url": pricing_page.DEFAULT_URL,
            "combinations": results,
            "api_captured_count": len(pricing_page.api_captured),
            "api_responses": pricing_page.api_captured,
        }
        path = save_result(output, prefix="precision-render-ui-pricing", suffix="-all")

        # 7. 打印汇总
        lines = ["\n" + "=" * 80, "精准渲染定价采集汇总（7 组合）", "=" * 80]
        lines.append(f"{'创作模式':<12} {'子模式':<20} {'价格(知点)':<12} {'余额':<10}")
        lines.append("-" * 60)
        for r in results:
            sub_label = r.get("sub_mode", r["deep_mode"])
            lines.append(
                f"{r['creation_mode']:<12} {sub_label:<20} "
                f"{r['price_text']:<12} {r['coin_balance']:<10}"
            )
        lines.append(f"\nAPI 拦截数: {len(pricing_page.api_captured)}")
        lines.append(f"结果文件: {path}")
        lines.append("=" * 80)
        print("\n".join(lines))

    @pytest.mark.core
    def test_api_ui_consistency(self, pricing_session, assertion):
        """校验 API 返回价格与 UI 显示价格一致（精准渲染×标准模式）。"""
        page, token = pricing_session

        # UI 采集
        pricing_page = PrecisionRenderPricingPage(page, auto_close_popups=False)
        pricing_page.goto()
        pricing_page.enable_api_intercept()

        # 精准渲染 × 标准模式
        ui_result = pricing_page.capture_combination_price(0, 0)
        ui_price = ui_result.get("price_value")

        # API 查询
        api_resp = fetch_price(token, _API_CASES[0].params)
        api_amount = api_resp.get("data", {}).get("amount") if isinstance(api_resp.get("data"), dict) else None

        # 校验 API 与 UI 一致性
        if ui_price is not None and api_amount is not None:
            assertion.assert_equal(
                api_amount, ui_price,
                name="api_ui_price_consistency",
                message=f"API amount({api_amount}) 应与 UI price({ui_price}) 一致",
            )

        # baseline 校验
        expected_price = get_expected_price("精准渲染", "标准模式", "新钻石会员")
        if api_amount is not None and expected_price is not None:
            assertion.assert_equal(
                api_amount, expected_price,
                name="api_baseline_consistency",
            )


# ── API 测试类 ────────────────────────────────────────────────────────────────
class TestAPIPrecisionRenderPricing:
    """API 价格查询测试。"""

    @pytest.mark.parametrize("case_data", _API_CASES, ids=_API_IDS)
    @pytest.mark.core
    def test_api_price_query(
        self,
        case_data: APIPricingCase,
        assertion,
    ):
        """直接调用 aiDrawPrice 接口查询价格。"""
        # 1. API 登录
        token = api_login()

        # 2. 调用价格接口
        resp = fetch_price(token, case_data.params)
        data = resp.get("data", {})

        # 校验接口返回成功
        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"),
            "0",
            name=f"{case_data.case_id}_api_success",
        )

        # 校验 data 是 dict
        assertion.assert_true(
            isinstance(data, dict),
            name=f"{case_data.case_id}_data_is_dict",
            message=f"data 应为 dict，实际类型: {type(data).__name__}",
        )

        if isinstance(data, dict):
            amount = data.get("amount")
            # 校验价格为正整数
            assertion.assert_true(
                isinstance(amount, (int, float)) and amount > 0,
                name=f"{case_data.case_id}_amount_positive",
                message=f"amount 应为正数，实际: {amount}",
            )

            # 从 baseline 获取预期值（统一数据源）
            # 解析 product-combination（格式："精准渲染-标准模式"）
            expected_amount = None
            parts = case_data.scenario_name.split("-", 1)
            if len(parts) == 2:
                expected_amount = get_expected_price(parts[0], parts[1], "新钻石会员")
            if expected_amount is not None:
                assertion.assert_equal(
                    amount,
                    expected_amount,
                    name=f"{case_data.case_id}_amount_expected",
                )
