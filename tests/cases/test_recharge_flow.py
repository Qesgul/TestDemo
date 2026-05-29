"""充值弹窗信息获取流程测试用例。

测试范围：
- 14 个 data_value 参数化（对应 userPayIdentityV2 接口不同身份场景）
- 每个 data_value：mock 接口 → 点击充值按钮 → 校验弹窗 → 抓套餐 → 关闭

测试约定：
- 入口 URL：ModelDetailPage.DEFAULT_URL（唯一配置点）
- 接口 mock：ModelDetailPage.mock_user_pay_identity(data_value)
- 断言：统一走 assertion fixture，全部带 name= 接入 checkpoint summary
"""
import logging

import pytest

from data_types.recharge_data_types import RechargeCaseData
from pages.methods.login_page import LoginPage
from pages.methods.model_detail_page import ModelDetailPage
from tests.steps.test_base import case_ids, load_typed_cases_from_yaml
from common.tracking.expectations import load_gio_expectations

_logger = logging.getLogger(__name__)

_DATA_PATH = "tests/data/recharge_flow_data.yaml"
_CASES = load_typed_cases_from_yaml(_DATA_PATH, RechargeCaseData)
_CASE_IDS = case_ids(_CASES)

if not _CASES:
    pytest.skip(
        "未匹配到可执行的 RechargeCaseData，请检查 settings.yaml 中 execution.tags 过滤条件",
        allow_module_level=True,
    )


class TestRechargeFlow:
    """充值弹窗信息获取流程。"""

    @pytest.mark.parametrize("case_data", _CASES, ids=_CASE_IDS)
    @pytest.mark.core
    @pytest.mark.ui
    @pytest.mark.popup
    def test_recharge_modal_with_mocked_identity(
        self, case_data: RechargeCaseData, page, assertion,
    ):
        """对 data_value=N 场景：mock 接口 → 触发弹窗 → 校验套餐 → 关闭。

        步骤：
          1. Cookie 登录（无 cookie 走密码登录）
          2. 进入 3D 模型详情页
          3. mock userPayIdentityV2 返回 data=N
          4. 点击充值按钮，等待弹窗
          5. 抓取套餐列表
          6. 关闭弹窗
        """
        _logger.info("=== 用例 %s | data_value=%d ===",
                     case_data.case_name, case_data.data_value)

        # ── 步骤 1：登录 ──────────────────────────────────────
        login_page = LoginPage(page)
        login_page.goto_login_page()
        login_page.login_with(case_data.username, case_data.password)
        page.wait_for_timeout(3000)

        assertion.assert_true(
            "login" not in page.url.lower(),
            name="登录跳转成功",
            message=f"登录后仍在登录页：{page.url}",
        )

        # ── 步骤 2：进入 3D 模型详情页 ─────────────────────
        model_page = ModelDetailPage(page)
        model_page.goto()

        assertion.assert_in(
            "3dmoxing",
            page.url,
            name="详情页加载完成",
            message=f"未进入预期详情页：{page.url}",
        )

        # ── 步骤 3：mock 接口（必须在点击充值按钮之前）──
        model_page.mock_user_pay_identity(case_data.data_value)

        # ── 步骤 4：点击充值按钮 → 验证弹窗显示 ──────────
        model_page.click_recharge_button()

        assertion.assert_true(
            model_page.is_recharge_modal_visible(),
            name="充值弹窗显示",
            message=f"data={case_data.data_value} 充值弹窗未显示",
        )

        # ── 步骤 5：抓取套餐列表 → 验证非空 ───────────────
        packages = model_page.get_recharge_packages()

        assertion.assert_true(
            len(packages) >= 1,
            name="套餐数量达到 1",
            message=f"data={case_data.data_value} 套餐数量为 0",
        )

        # 记录套餐信息到日志（debug 级，不污染默认输出）
        for i, pkg in enumerate(packages, 1):
            _logger.debug("套餐 [%d]: %s", i, pkg)

        # ── 步骤 6：关闭弹窗 ──────────────────────────────────
        model_page.close_recharge_modal()
        page.wait_for_timeout(500)

        assertion.assert_false(
            model_page.is_recharge_modal_visible(),
            name="充值弹窗关闭",
            message="关闭操作后弹窗仍可见",
        )

        # ── 清理 mock（避免影响下一个参数化用例）─────────
        model_page.unmock_user_pay_identity()

    @pytest.mark.core
    @pytest.mark.ui
    def test_recharge_gio_tracking(self, page, assertion, gio_tracking):
        """充值需求 GIO 埋点捕获校验（复用现有页面方法）。

        标识符必校；var 可选；pending 状态埋点（支付成功）本期跳过。
        """
        expects = load_gio_expectations(_DATA_PATH)
        first = _CASES[0]

        # ── 登录（被动捕获 Rechargetest_2）──
        login_page = LoginPage(page)
        login_page.goto_login_page()
        login_page.login_with(first.username, first.password)
        page.wait_for_timeout(3000)

        # ── 进入详情页 + mock 身份（保证弹窗有套餐）──
        model_page = ModelDetailPage(page)
        model_page.goto()
        model_page.mock_user_pay_identity(first.data_value)

        # ── 点充值按钮 → 弹窗曝光 ──
        model_page.click_recharge_button()
        assertion.assert_true(
            model_page.is_recharge_modal_visible(),
            name="充值弹窗显示", message="充值弹窗未显示，无法验证曝光埋点",
        )
        gio_tracking.assert_event("sc_coinrecharge_show")

        # ── 选中套餐 → 选中埋点 ──
        model_page.select_package(0)
        gio_tracking.assert_event("sc_coinrecharge_click")

        # ── 登录实验/对照组变量埋点（流程被动捕获）──
        gio_tracking.assert_event("Rechargetest_2")

        # ── pending 埋点（如支付成功）本期跳过 ──
        for exp in expects:
            if exp.is_pending:
                _logger.info("埋点 %s 标记 pending，本期跳过校验", exp.identifier)

        model_page.unmock_user_pay_identity()


if __name__ == "__main__":
    import subprocess
    import sys

    sys.exit(subprocess.call([
        sys.executable, "-m", "pytest", __file__,
        "-v", "--headed", "-s",
    ]))
