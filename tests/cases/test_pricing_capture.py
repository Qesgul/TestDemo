# -*- coding: utf-8 -*-
"""Agent 模式定价采集 - 自动化测试套件

覆盖范围：
  UI-ALL    单次登录遍历全部模型，采集价格 + baseline 校验
  API-001~  API 接口价格查询（无浏览器）
  API-UI    API/UI 一致性校验

登录策略：
  UI 测试：class 级 fixture 单次登录，遍历全部模型
  API 测试：每个测试方法自行 API 登录（不涉及浏览器）

运行方式：
  # 全量
  pytest tests/cases/test_pricing_capture.py --override-ini="addopts=-q -s --headed" -v

  # 仅 UI
  pytest tests/cases/test_pricing_capture.py -k "ui" --override-ini="addopts=-q -s --headed" -v

  # 仅 API
  pytest tests/cases/test_pricing_capture.py -k "api" --override-ini="addopts=-q -s" -v
"""

from datetime import datetime

import pytest

from common.pricing import (
    get_expected_price,
    get_member_account,
    list_members,
)
from common.pricing_helpers import api_login, inject_cookie, fetch_price, save_result
from pages.methods.pricing_capture_page import PricingCapturePage

# 强制定价测试在同一 worker 串行执行，避免多设备登录被踢
pytestmark = pytest.mark.xdist_group("pricing")

# 默认只用新钻石会员执行（调试阶段）。
# 扩展为全部已配置会员：改为 _DEFAULT_MEMBERS = None
_DEFAULT_MEMBERS = ["新钻石会员"]

_CONFIGURED_MEMBERS = (
    _DEFAULT_MEMBERS
    if _DEFAULT_MEMBERS is not None
    else [m for m in list_members() if get_member_account(m) is not None]
)

# Agent 模式的 3 种模型
_AGENT_MODELS = ["GPT Image 2", "Nano Banana Pro", "Nano Banana 2"]

# API 查询场景（从 baseline 提取）
_API_SCENARIOS = [
    {
        "name": "Agent模式-GPT Image 2",
        "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701",
                    "isIntelligentAgentTask": 1, "bananaChannel": 4},
        "product": "Agent模式", "combination": "GPT Image 2",
    },
    {
        "name": "Agent模式-Nano Banana Pro",
        "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701",
                    "isIntelligentAgentTask": 1, "bananaChannel": 1},
        "product": "Agent模式", "combination": "Nano Banana Pro",
    },
    {
        "name": "Agent模式-Nano Banana 2",
        "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701",
                    "isIntelligentAgentTask": 1, "bananaChannel": 3},
        "product": "Agent模式", "combination": "Nano Banana 2",
    },
]


# ── class 级 fixture：UI 测试类共享一次登录 ─────────────────────────────────
@pytest.fixture(scope="class")
def pricing_session(request, browser):
    """Class 级登录 fixture：独立 context/page，不干扰 pytest-playwright 的 page。

    扩展多账号时：@pytest.fixture(params=_CONFIGURED_MEMBERS, ids=_CONFIGURED_MEMBERS)
    """
    member = getattr(request, "param", _DEFAULT_MEMBERS[0])
    context = browser.new_context()
    page = context.new_page()
    token = api_login(member)
    inject_cookie(page, token)
    yield page, token, member
    page.close()
    context.close()


# ── UI 测试 ───────────────────────────────────────────────────────────────────
class TestAgentUIPricing:
    """Agent 模式 UI 定价采集（class 级单次登录，遍历全部模型）。"""

    @pytest.mark.core
    def test_agent_pricing(self, pricing_session, assertion):
        """单次登录遍历全部模型，采集价格并校验。"""
        page, token, member = pricing_session

        # 2. 导航到 agent 页（只做一次）
        pricing_page = PricingCapturePage(page, auto_close_popups=False)
        pricing_page.goto()
        pricing_page.enable_api_intercept()

        # 3. 遍历所有模型（一次开下拉，逐个切换）
        results = pricing_page.capture_all_models()

        assertion.assert_true(
            len(results) >= 2,
            name=f"{member}_model_count",
            message=f"至少应有 2 个模型，实际: {len(results)}",
        )

        # 4. 逐模型校验
        for r in results:
            model_name = r["model_name"]

            # 价格非空
            assertion.assert_true(
                r["price_text"] != "",
                name=f"{member}_{model_name}_price_not_empty",
                message=f"{model_name} 价格不应为空",
            )

            # 价格为正整数
            if r["price_value"] is not None:
                assertion.assert_true(
                    r["price_value"] > 0,
                    name=f"{member}_{model_name}_price_positive",
                )

            # baseline 预期价格校验
            expected = get_expected_price("Agent模式", model_name, member)
            if expected is not None:
                assertion.assert_equal(
                    r["price_value"],
                    expected,
                    name=f"{member}_{model_name}_price_expected",
                )

        # 5. 保存结果
        output = {
            "capture_time": datetime.now().isoformat(),
            "source": "ui",
            "member": member,
            "page_url": pricing_page.DEFAULT_URL,
            "models": results,
            "api_captured_count": len(pricing_page.api_captured),
        }
        save_result(output, prefix="ui-pricing", suffix=f"-{member}")

        # 6. 打印汇总
        lines = [f"\n{'=' * 70}", f"UI 定价采集 — {member}", "=" * 70]
        lines.append(f"{'模型':<20} {'描述':<30} {'价格':<10} {'预期':<10}")
        lines.append("-" * 70)
        for r in results:
            expected = get_expected_price("Agent模式", r["model_name"], member)
            lines.append(
                f"{r['model_name']:<20} {r['model_desc']:<30} "
                f"{r['price_text']:<10} {expected or '-':<10}"
            )
        lines.append(f"\nAPI 拦截数: {len(pricing_page.api_captured)}")
        lines.append("=" * 70)
        print("\n".join(lines))

    @pytest.mark.core
    def test_api_ui_consistency(self, pricing_session, assertion):
        """校验 API 返回价格与 UI 显示价格一致。"""
        page, token, member = pricing_session

        # UI 采集
        pricing_page = PricingCapturePage(page, auto_close_popups=False)
        pricing_page.goto()
        pricing_page.enable_api_intercept()
        ui_result = pricing_page.capture_model_price(0)
        ui_price = ui_result.get("price_value")

        # API 查询
        api_resp = fetch_price(token, _API_SCENARIOS[0]["params"])
        api_amount = api_resp.get("data", {}).get("amount") if isinstance(api_resp.get("data"), dict) else None

        # 一致性校验
        if ui_price is not None and api_amount is not None:
            assertion.assert_equal(
                api_amount, ui_price,
                name="api_ui_consistency",
                message=f"API({api_amount}) 应与 UI({ui_price}) 一致",
            )

        # baseline 校验
        expected = get_expected_price("Agent模式", "GPT Image 2", member)
        if api_amount is not None and expected is not None:
            assertion.assert_equal(
                api_amount, expected,
                name="api_baseline_consistency",
            )


# ── API 测试 ──────────────────────────────────────────────────────────────────
class TestAgentAPIPricing:
    """Agent 模式 API 定价查询（无浏览器）。"""

    @pytest.mark.parametrize(
        "scenario", _API_SCENARIOS,
        ids=[s["name"] for s in _API_SCENARIOS],
    )
    @pytest.mark.core
    def test_api_price(self, scenario: dict, assertion):
        """调用 API 查询价格，与 baseline 比对。"""
        token = api_login("新钻石会员")
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {})

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(data, dict),
            name=f"{scenario['name']}_data_type",
        )

        if isinstance(data, dict):
            amount = data.get("amount")
            assertion.assert_true(
                isinstance(amount, (int, float)) and amount > 0,
                name=f"{scenario['name']}_amount_positive",
            )

            expected = get_expected_price(
                scenario["product"], scenario["combination"], "新钻石会员"
            )
            if expected is not None:
                assertion.assert_equal(
                    amount, expected,
                    name=f"{scenario['name']}_amount_expected",
                )
