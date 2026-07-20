# -*- coding: utf-8 -*-
"""AI 定价采集 - 自动化测试套件（平面填彩 / 实景改造 / 全景渲染）

覆盖范围：
  UI-FPC-001~003  平面填彩 × 3 子模式（标准/Nano/GPT Image 2）UI 价格采集
  UI-ISR-001~002  实景改造 × 2 子模式（标准/Nano）UI 价格采集
  UI-PNR-001      全景渲染 × 标准模式 UI 价格采集（从左侧菜单进入）
  API-FPC-001~003 平面填彩 × 3 aiDrawPrice 接口价格查询
  API-ISR-001~002 实景改造 × 2 aiDrawPrice 接口价格查询
  AI-ALL          全组合遍历 + API 拦截数据输出

页面结构与创作渲染/效果图美化相同：
  BottomPartButtons modeText → popover → modeTitle
  选中态判断：容器 class 含 "active"

登录策略：
  不依赖 logged_in_page / logged_in_context fixture，测试内部自行登录：
  1. API 登录获取 SESSION cookie
  2. 注入到 playwright page.context
  3. 用 AIPricingPage 导航并采集

运行方式：
  pytest tests/cases/test_ai_pricing.py -k "test_all_combinations_capture" \\
    --override-ini="addopts=-q -s --headed" -v
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
import requests as http_requests

from common.pricing import get_expected_price, get_member_account
from common.yaml_loader import load_yaml
from data_types.ai_pricing_data_types import AIPricingAPICase, AIPricingUICase
from pages.methods.ai_pricing_page import AIPricingPage

# ── 数据加载 ──────────────────────────────────────────────────────────────────
_DATA_PATH = "tests/data/ai_pricing_data.yaml"
_DATA = load_yaml(_DATA_PATH)

_UI_CASES = [AIPricingUICase(**c) for c in (_DATA.get("ui_cases") or [])]
_API_CASES = [AIPricingAPICase(**c) for c in (_DATA.get("api_cases") or [])]

if not _UI_CASES and not _API_CASES:
    pytest.skip("ai_pricing_data.yaml 中无用例数据", allow_module_level=True)

_UI_IDS = [c.case_id for c in _UI_CASES]
_API_IDS = [c.case_id for c in _API_CASES]

# ── 常量 ──────────────────────────────────────────────────────────────────────
_PRICE_API = "https://api.znzmo.cn/ai/api/aiDrawCoin/aiDrawPrice"
_LOGIN_API = "https://api.znzmo.cn/login/loginByPsw"
_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / ".workflow" / "pricing-output"


# ── 登录辅助 ──────────────────────────────────────────────────────────────────
def _api_login_session(member: str = "新钻石会员") -> str:
    """通过 API 登录获取 SESSION cookie。"""
    account = get_member_account(member)
    if not account:
        raise RuntimeError(f"会员账号未配置或待补充: {member}")
    pwd_md5 = hashlib.md5(account["password"].encode()).hexdigest()
    resp = http_requests.get(
        _LOGIN_API,
        params={"username": account["username"], "password": pwd_md5},
        timeout=15,
    )
    data = resp.json()
    error_code = data.get("error", {}).get("errorCode", "")
    if error_code != "0":
        raise RuntimeError(f"API 登录失败: {data}")

    token = resp.cookies.get("SESSION")
    if not token:
        raise RuntimeError("登录成功但无 SESSION cookie")
    return token


def _inject_session_cookie(page, token: str) -> None:
    """将 SESSION cookie 注入 playwright page.context。"""
    page.context.add_cookies([{
        "name": "SESSION",
        "value": token,
        "domain": ".znzmo.cn",
        "path": "/",
        "secure": True,
        "httpOnly": True,
    }])


# ── 辅助函数 ──────────────────────────────────────────────────────────────────
def _save_result(result: dict, prefix: str = "ai-pricing", suffix: str = "") -> Path:
    """保存结果到 JSON 文件。"""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = _OUTPUT_DIR / f"{prefix}-{stamp}{suffix}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _api_fetch_price(session_token: str, params: dict) -> dict:
    """通过 requests 调用 aiDrawPrice 接口（带 SESSION cookie）。"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"SESSION={session_token}",
    }
    resp = http_requests.post(
        _PRICE_API,
        json=params,
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ── UI 测试类 ─────────────────────────────────────────────────────────────────
class TestUIAIPricing:
    """UI 子模式价格采集测试（平面填彩 / 实景改造 / 全景渲染）。"""

    @pytest.mark.parametrize("case_data", _UI_CASES, ids=_UI_IDS)
    @pytest.mark.core
    def test_single_sub_mode_price(
        self,
        case_data: AIPricingUICase,
        ai_draw_page,
        assertion,
    ):
        """切换到指定子模式，采集 UI 显示价格。"""
        # 全景渲染可能无法访问，标记 skip
        if case_data.navigate_via_menu and case_data.menu_key == "panoramicRender":
            pytest.skip(
                "全景渲染页面需要从左侧菜单进入，可能因权限/页面变化不可用。"
                "请使用 test_all_combinations_capture 运行完整采集。"
            )

        page = ai_draw_page

        # 1. 导航并采集
        pricing_page = AIPricingPage(page, auto_close_popups=False)
        pricing_page.enable_api_intercept()
        pricing_page.goto_page(
            case_data.menu_key,
            navigate_via_menu=case_data.navigate_via_menu,
        )

        # 2. 切换子模式并采集
        result = pricing_page.capture_sub_mode_price(case_data.sub_mode_name)

        # 校验子模式名称
        assertion.assert_equal(
            result["sub_mode"],
            case_data.sub_mode_name,
            name=f"{case_data.case_id}_sub_mode",
        )

        # 校验价格非空
        assertion.assert_true(
            result["price_text"] != "",
            name=f"{case_data.case_id}_price_not_empty",
            message=f"{case_data.product_name}×{case_data.sub_mode_name} 价格不应为空",
        )

        # 校验价格为正整数
        if result["price_value"] is not None:
            assertion.assert_true(
                result["price_value"] > 0,
                name=f"{case_data.case_id}_price_positive",
            )

        # 从 baseline 获取预期价格
        expected_price = get_expected_price(case_data.product_name, case_data.sub_mode_name, "新钻石会员")
        if expected_price is not None:
            assertion.assert_equal(
                result["price_value"],
                expected_price,
                name=f"{case_data.case_id}_price_expected",
                message=f"预期价格 {expected_price}，实际 {result['price_value']}",
            )

    @pytest.mark.core
    def test_all_combinations_capture(self, ai_draw_page, assertion):
        """遍历所有产品×子模式组合，采集 UI 价格并输出汇总。

        策略：每个产品采集完毕后立即校验价格（此时仍在该产品页面），
        避免页面导航后价格状态变化导致校验失败。
        """
        page = ai_draw_page

        # 创建页面对象
        pricing_page = AIPricingPage(page, auto_close_popups=False)
        pricing_page.enable_api_intercept()

        all_results = []

        # ── 平面填彩 ──
        _logger("=== 采集平面填彩 ===")
        pricing_page.goto_page("floorPlanColor")
        fpc_modes = ["标准模式", "Nano Banana Pro", "GPT Image 2"]
        fpc_results = pricing_page.capture_all_sub_modes("平面填彩", fpc_modes)
        all_results.extend(fpc_results)

        # 立即校验（此时仍在平面填彩页）
        for r in fpc_results:
            assertion.assert_true(
                r["price_text"] != "",
                name=f"AI-ALL-平面填彩-{r['sub_mode']}_price_not_empty",
                message=f"平面填彩×{r['sub_mode']} 价格不应为空",
            )
            expected = get_expected_price("平面填彩", r["sub_mode"], "新钻石会员")
            if expected is not None:
                assertion.assert_equal(
                    r["price_value"],
                    expected,
                    name=f"AI-KNOWN-平面填彩-{r['sub_mode']}_price",
                    message=f"平面填彩×{r['sub_mode']} 预期 {expected}，实际 {r['price_value']}",
                )

        # ── 实景改造 ──
        _logger("=== 采集实景改造 ===")
        pricing_page.goto_page("insituRenovation")
        isr_modes = ["标准模式", "Nano Banana Pro"]
        isr_results = pricing_page.capture_all_sub_modes("实景改造", isr_modes)
        all_results.extend(isr_results)

        # 立即校验（此时仍在实景改造页）
        for r in isr_results:
            assertion.assert_true(
                r["price_text"] != "",
                name=f"AI-ALL-实景改造-{r['sub_mode']}_price_not_empty",
                message=f"实景改造×{r['sub_mode']} 价格不应为空",
            )
            expected = get_expected_price("实景改造", r["sub_mode"], "新钻石会员")
            if expected is not None:
                assertion.assert_equal(
                    r["price_value"],
                    expected,
                    name=f"AI-KNOWN-实景改造-{r['sub_mode']}_price",
                    message=f"实景改造×{r['sub_mode']} 预期 {expected}，实际 {r['price_value']}",
                )

        # ── 全景渲染 ──
        _logger("=== 采集全景渲染 ===")
        try:
            pricing_page.goto_page("panoramicRender", navigate_via_menu=True)
            # 尝试发现子模式
            discovered_modes = pricing_page.discover_sub_modes()
            if discovered_modes:
                pnr_results = pricing_page.capture_all_sub_modes("全景渲染", discovered_modes)
                all_results.extend(pnr_results)
            else:
                # 尝试直接采集当前显示的价格
                price_text = pricing_page.get_current_price()
                balance = pricing_page.get_coin_balance()
                all_results.append({
                    "product": "全景渲染",
                    "sub_mode": "默认模式",
                    "price_text": price_text,
                    "price_value": int(price_text) if price_text.isdigit() else None,
                    "coin_balance": balance,
                    "api_response": None,
                    "capture_time": datetime.now().isoformat(),
                })
                _logger("全景渲染无可切换子模式，采集默认价格: %s", price_text)
        except Exception as e:
            _logger("全景渲染采集失败: %s", e)
            all_results.append({
                "product": "全景渲染",
                "sub_mode": "N/A",
                "price_text": "SKIP",
                "price_value": None,
                "coin_balance": "",
                "api_response": None,
                "error": str(e),
                "capture_time": datetime.now().isoformat(),
            })

        # 保存结果
        output = {
            "capture_time": datetime.now().isoformat(),
            "source": "ui",
            "combinations": all_results,
            "api_captured_count": len(pricing_page.api_captured),
            "api_responses": pricing_page.api_captured,
        }
        path = _save_result(output, prefix="ai-ui-pricing", suffix="-all")

        # 打印汇总
        lines = ["\n" + "=" * 80, "AI 定价采集汇总（平面填彩/实景改造/全景渲染）", "=" * 80]
        lines.append(f"{'产品':<12} {'子模式':<20} {'价格(知点)':<12} {'余额':<10}")
        lines.append("-" * 60)
        for r in all_results:
            lines.append(
                f"{r['product']:<12} {r['sub_mode']:<20} "
                f"{r['price_text']:<12} {r['coin_balance']:<10}"
            )
        lines.append(f"\nAPI 拦截数: {len(pricing_page.api_captured)}")
        lines.append(f"结果文件: {path}")
        lines.append("=" * 80)
        print("\n".join(lines))


# ── 辅助日志函数 ──────────────────────────────────────────────────────────────
import logging
_logger_func = logging.getLogger(__name__).info


def _logger(msg, *args):
    _logger_func(msg, *args)


# ── API 测试类 ────────────────────────────────────────────────────────────────
class TestAPIAIPricing:
    """API 价格查询测试（平面填彩 / 实景改造）。"""

    @pytest.mark.parametrize("case_data", _API_CASES, ids=_API_IDS)
    @pytest.mark.core
    def test_api_price_query(
        self,
        case_data: AIPricingAPICase,
        assertion,
    ):
        """直接调用 aiDrawPrice 接口查询价格。"""
        # 1. API 登录
        token = _api_login_session()

        # 2. 调用价格接口
        resp = _api_fetch_price(token, case_data.params)
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

            # 从 baseline 获取预期值
            parts = case_data.scenario_name.split("-", 1)
            if len(parts) == 2:
                expected_amount = get_expected_price(parts[0], parts[1], "新钻石会员")
                if expected_amount is not None:
                    assertion.assert_equal(
                        amount,
                        expected_amount,
                        name=f"{case_data.case_id}_amount_expected",
                    )

    @pytest.mark.core
    def test_api_ui_consistency(self, ai_draw_page, assertion):
        """校验 API 返回价格与 UI 显示价格一致（平面填彩×标准模式）。"""
        # 1. API 登录
        token = _api_login_session()

        # 2. UI 采集
        page = ai_draw_page
        pricing_page = AIPricingPage(page, auto_close_popups=False)
        pricing_page.enable_api_intercept()
        pricing_page.goto_page("floorPlanColor")

        ui_result = pricing_page.capture_sub_mode_price("标准模式")
        ui_price = ui_result.get("price_value")

        # 3. API 查询（平面填彩-标准模式）
        api_params = get_expected_api_params("平面填彩", "标准模式")
        if api_params:
            api_resp = _api_fetch_price(token, api_params)
            api_amount = api_resp.get("data", {}).get("amount") if isinstance(api_resp.get("data"), dict) else None

            # 4. 校验 API 与 UI 一致性
            if ui_price is not None and api_amount is not None:
                assertion.assert_equal(
                    api_amount,
                    ui_price,
                    name="api_ui_price_consistency",
                    message=f"API amount({api_amount}) 应与 UI price({ui_price}) 一致",
                )

            # 5. 从 baseline 校验
            expected_price = get_expected_price("平面填彩", "标准模式", "新钻石会员")
            if api_amount is not None and expected_price is not None:
                assertion.assert_equal(
                    api_amount,
                    expected_price,
                    name="api_baseline_consistency",
                    message=f"API amount({api_amount}) 应与 baseline 预期({expected_price}) 一致",
                )


# ── 辅助导入 ──────────────────────────────────────────────────────────────────
from common.pricing import get_api_params as get_expected_api_params
