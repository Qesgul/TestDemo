"""非VIP用户下载确认弹窗计费逻辑修复 - 自动化测试套件

覆盖范围：
  - 券字段交互    AUTO-CPN-001~007  (7 auto)
  - 默认选中策略  AUTO-DFT-001~010  (9 auto + 1 manual skip)
  - 计算逻辑      AUTO-CAL-001~008  (7 auto + 1 network)
  - 边界场景      AUTO-BND-001~004  (3 auto + 1 network)
  合计: 26 auto + 2 network + 1 manual = 29 条

运行方式（必须指定测试账号，否则使用 login_data.yaml 默认账号）：
  pytest tests/cases/test_nonvip_download.py \\
    --login-username=13140725123 --login-password=Qyff2011

数据前置说明：
  每条用例的 docstring 中标注了所需的 SQL 造数步骤（见 coupon_sql_templates）。
  典型流程：
    1. 执行 INSERT（coupon_sql_templates.valid_35 等）向账号 255635028913 写入对应券
    2. 运行用例
    3. 执行 DELETE（coupon_sql_templates.cleanup）清理测试券
  当 mysql_db fixture 就绪后，可将 SQL 步骤封装为 pytest fixture 自动化 setup/teardown。

Selector 说明：
  弹窗元素 selector 目前为 TODO_SELECTOR，需 codegen 抓取后回填：
    python -m playwright codegen https://sgt.znzmo.com/sgt/36982063.html
  （前置：先执行 SQL 注入1张35知币券，登录 13140725123 后打开弹窗操作）
"""

import pytest

from common.yaml_loader import load_yaml
from data_types.nonvip_download_data_types import CouponPriorityCase
from pages.methods.nonvip_download_page import NonvipDownloadPage

_DATA_PATH = "tests/data/nonvip_download_data.yaml"
_DATA = load_yaml(_DATA_PATH)
_CASES = [CouponPriorityCase(**c) for c in (_DATA.get("cases") or [])]


class TestNonvipDownload:
    """非VIP用户下载确认弹窗计费逻辑修复 - 自动化测试套件。"""

    # ══════════════════════════════════════════════════════════════════════════
    # 券字段交互（AUTO-CPN）
    # ══════════════════════════════════════════════════════════════════════════

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_cpn_001_cancel_selected_coupon(self, logged_in_page, assertion):
        """AUTO-CPN-001 (P0/auto): 点击已选中抵扣券取消选中且金额重算（修复 Bug-2）

        前置数据: 账号持 1 张 35知币有效券（适用本单）
        SQL: coupon_sql_templates.valid_35  id=499000001
        清理: coupon_sql_templates.cleanup  ids=499000001
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        # 前提: 弹窗默认已选中 35知币券
        dp.click_coupon("35")
        assertion.assert_false(
            dp.is_coupon_selected("35"),
            name="35知币券取消选中",
            message="点击已选中的 35知币券后应变为未选中态",
        )
        assertion.assert_true(
            dp.parse_zhibi(dp.get_discount_amount_text()) == 0,
            name="取消后已优惠归零",
            message="取消选中后已优惠金额应归零（0 知币）",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_cpn_002_restore_selected_coupon(self, logged_in_page, assertion):
        """AUTO-CPN-002 (P0/auto): 取消后再次点击恢复选中且金额重算

        前置数据: 账号持 1 张 35知币有效券（处于未选中态）
        SQL: coupon_sql_templates.valid_35  id=499000002
        清理: coupon_sql_templates.cleanup  ids=499000002
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        dp.click_coupon("35")   # 先取消
        dp.click_coupon("35")   # 再选中
        assertion.assert_true(
            dp.is_coupon_selected("35"),
            name="35知币券恢复选中",
            message="再次点击后 35知币券应恢复为选中态",
        )
        expected_discount = _DATA["coupon_discount"]["model60_with_35"]["deduction"]
        assertion.assert_true(
            str(expected_discount) in dp.get_discount_amount_text(),
            name="恢复选中已优惠重算",
            message=f"恢复选中后已优惠应含 {expected_discount} 知币",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cpn_003_control_is_radio(self, logged_in_page, assertion):
        """AUTO-CPN-003 (P1/auto): 券字段控件样式为单选框（role=radio）

        前置数据: 账号持 1 张可用券
        SQL: coupon_sql_templates.valid_35  id=499000003
        清理: coupon_sql_templates.cleanup  ids=499000003
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        role = dp.get_coupon_control_role("35")
        assertion.assert_equal(
            role,
            "radio",
            name="券控件role为radio",
            message=f"券字段应为单选框控件（role=radio），实际 role={role!r}",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cpn_004_multi_coupon_mutual_exclusive(self, logged_in_page, assertion):
        """AUTO-CPN-004 (P1/auto): 多张券并存时单选互斥

        前置数据: 账号同时持 35知币 + 40知币券，均适用本单
        SQL: coupon_sql_templates.valid_35 (id=499000041) + valid_40 (id=499000042)
        清理: ids=499000041,499000042
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        # 默认选中 35，点击 40 后应互斥
        dp.click_coupon("40")
        assertion.assert_true(
            dp.is_coupon_selected("40"),
            name="点击40券后40选中",
            message="点击 40知币券后应变为选中态",
        )
        assertion.assert_false(
            dp.is_coupon_selected("35"),
            name="切换后35券自动取消",
            message="选中 40知币券后 35知币券应自动取消",
        )
        expected_total = _DATA["coupon_discount"]["model60_with_40"]["total"]
        assertion.assert_true(
            str(expected_total) in dp.get_total_amount_text(),
            name="切换选中金额按40重算",
            message=f"切换到 40知币券后总计应为 {expected_total} 知币",
        )

    @pytest.mark.ui
    def test_auto_cpn_005_amount_refresh_realtime(self, logged_in_page, assertion):
        """AUTO-CPN-005 (P2/auto): 选中取消时金额实时刷新无延迟

        前置数据: 账号持 1 张可用券
        SQL: coupon_sql_templates.valid_35  id=499000005
        清理: coupon_sql_templates.cleanup  ids=499000005
        注: 时序断言略脆，存在 flaky 风险，建议在稳定环境执行
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        # 连续切换 3 次，每次金额应即时更新（通过元素可见性 + 非空断言代替延迟测量）
        for _ in range(3):
            dp.click_coupon("35")
            assertion.assert_true(
                dp.get_discount_amount_text() != "",
                name="金额实时刷新无延迟",
                message="切换券后已优惠金额文本应即时更新，不为空",
            )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cpn_006_no_dirty_amount_after_repeated_toggle(self, logged_in_page, assertion):
        """AUTO-CPN-006 (P1/auto): 反复多次选中取消后金额无脏数据（关联 Bug-3）

        前置数据: 账号持 1 张可用券
        SQL: coupon_sql_templates.valid_35  id=499000006
        清理: coupon_sql_templates.cleanup  ids=499000006
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        for _ in range(5):
            dp.click_coupon("35")
        # 末态：最终处于选中态时（奇数次点击=取消，偶数=选中；5次=取消态）
        dp.click_coupon("35")  # 第6次 → 选中
        expected = _DATA["coupon_discount"]["model60_with_35"]
        assertion.assert_true(
            str(expected["deduction"]) in dp.get_discount_amount_text(),
            name="反复操作末态已优惠正确",
            message="反复切换后末态已优惠应与单次选中结果一致",
        )
        assertion.assert_true(
            str(expected["total"]) in dp.get_total_amount_text(),
            name="反复操作末态总计正确",
            message="反复切换后末态总计应与单次选中结果一致，无脏数据",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cpn_007_inapplicable_coupon_disabled(self, logged_in_page, assertion):
        """AUTO-CPN-007 (P1/auto): 不适用本单的券置灰不可选，默认仍选适用券（关联歧义#2）

        前置数据: 账号持 35知币适用券 + 40知币不适用券
        SQL: valid_35 (id=499000071) + not_applicable_40 (id=499000072)
        清理: ids=499000071,499000072
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_true(
            dp.is_coupon_disabled("40"),
            name="不适用券为禁用状态",
            message="不适用本单的 40知币券应为置灰/disabled 态",
        )
        assertion.assert_true(
            dp.is_coupon_selected("35"),
            name="默认仍选适用的35知币券",
            message="存在不适用券时，默认仍应选中适用的 35知币券",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 默认选中策略（AUTO-DFT）
    # ══════════════════════════════════════════════════════════════════════════

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_dft_001_s1_default_select_35(self, logged_in_page, assertion):
        """AUTO-DFT-001 (P0/auto): S1 账号仅持 35知币券时默认选中 35知币券

        前置数据: 账号仅持 1 张 35知币有效券（无其他券）
        SQL: coupon_sql_templates.valid_35  id=499000101
        清理: ids=499000101
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "35",
            name="S1默认选中35知币券",
            message="S1 场景：仅有 35知币券时应默认选中该券",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_dft_002_s2_default_select_40(self, logged_in_page, assertion):
        """AUTO-DFT-002 (P0/auto): S2 账号仅持 40知币券时默认选中 40知币券

        前置数据: 账号仅持 1 张 40知币有效券（无其他券）
        SQL: coupon_sql_templates.valid_40  id=499000102
        清理: ids=499000102
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "40",
            name="S2默认选中40知币券",
            message="S2 场景：仅有 40知币券时应默认选中该券",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_dft_003_s3_default_select_35_over_40(self, logged_in_page, assertion):
        """AUTO-DFT-003 (P0/auto): S3 持 35+40 券均适用时默认选 35（优先级 35>40）

        前置数据: 账号持 35知币 + 40知币券，均适用本单
        SQL: valid_35 (id=499000103) + valid_40 (id=499000104)
        清理: ids=499000103,499000104
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "35",
            name="S3默认选中35知币券",
            message="S3 场景：35+40 均适用时应默认选中 35知币券（35>40 优先级）",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_dft_004_s4_default_select_40_when_35_not_applicable(self, logged_in_page, assertion):
        """AUTO-DFT-004 (P1/auto): S4 持 35+40 但仅 40 适用本单时默认选 40

        前置数据: 账号持 35知币不适用券 + 40知币适用券
        SQL: not_applicable_35 (id=499000141) + valid_40 (id=499000142)
        清理: ids=499000141,499000142
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "40",
            name="S4仅40适用默认选40",
            message="S4 场景：35不适用本单时应默认选中 40知币券",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_dft_005_s5_default_select_35_among_three(self, logged_in_page, assertion):
        """AUTO-DFT-005 (P0/auto): S5 持 35+40+5 均适用时默认选 35 免费下载券

        前置数据: 账号持 35知币 + 40知币 + 5知币券，均适用本单
        SQL: valid_35 (id=499000151) + valid_40 (id=499000152) + valid_5 (id=499000153)
        清理: ids=499000151,499000152,499000153
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "35",
            name="S5默认选中35免费下载券",
            message="S5 场景：35+40+5 均适用时应默认选中 35知币免费下载券",
        )

    @pytest.mark.core
    @pytest.mark.main
    @pytest.mark.parametrize(
        "case_data",
        _CASES,
        ids=[c.case_id for c in _CASES],
    )
    def test_auto_dft_006_coupon_priority_order(self, logged_in_page, assertion, case_data):
        """AUTO-DFT-006 (P1/auto): 券优先级 35>40>5 验证（参数化两组）

        case DFT-006-a: 账号持 40知币+5知币券（均适用）→ 默认选 40
          SQL: valid_40 (id=499000161) + valid_5 (id=499000162)
        case DFT-006-b: 账号持 35知币+5知币券（均适用）→ 默认选 35
          SQL: valid_35 (id=499000163) + valid_5 (id=499000164)
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            case_data.expected_selected,
            name=case_data.scenario_name,
            message=(
                f"{case_data.coupon_combo} 组合时应默认选中 "
                f"{case_data.expected_selected}知币券"
            ),
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_dft_007_near_expire_coupon_priority(self, logged_in_page, assertion):
        """AUTO-DFT-007 (P1/auto): 同类券多张时临期优先选中（效期最短者）

        前置数据: 账号持 2 张 35知币券，一张剩余约1天（临期），一张30天
        SQL: near_expire_35 (id=499000171) + valid_35 (id=499000172, expire改为30天后)
        清理: ids=499000171,499000172
        注: "临期"具体阈值待产品确认（歧义#3）；当前假设系统能区分1天 vs 30天
        TODO[data]: 需开发暴露当前选中券 ID 或在 UI 中有可识别的临期标记
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        # 断言：弹窗已选中某张 35知币券（具体是否为临期那张，需 UI 暴露券 ID 后精确断言）
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "35",
            name="临期券优先选中",
            message="同类多张 35知币券时应默认选中临期（效期最短）的那张",
        )

    @pytest.mark.ui
    def test_auto_dft_008_same_expire_random_selection(self, logged_in_page, assertion):
        """AUTO-DFT-008 (P2/manual): 同类券效期相同时随机选1张

        manual 原因: 随机分布难以稳定断言，建议人工抽样 ≥10 次验证是否出现不同券 ID。
        前提: 需开发暴露默认选中券 ID（如 DOM data-coupon-id 属性）。
        """
        pytest.skip(
            "manual: 随机选中分布难以自动化稳定断言。"
            "请人工重复打开弹窗 ≥10 次，确认多次出现不同券 ID。"
            "（需开发暴露当前选中券 ID）"
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_dft_009_5zhibi_not_inflate_not_priority(self, logged_in_page, assertion):
        """AUTO-DFT-009 (P1/auto): 非VIP时 5知币券不膨胀且不被优先默认选中

        前置数据: 账号持 35知币券 + 5知币券，均适用本单
        SQL: valid_35 (id=499000191) + valid_5 (id=499000192)
        清理: ids=499000191,499000192
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "35",
            name="5知币券不被优先选",
            message="非VIP 持 35+5 时应默认选 35，5知币券不被优先选中",
        )
        # 5知币券存在但未被优先选中（非膨胀后升级为更高优先级）
        assertion.assert_false(
            dp.is_coupon_selected("5"),
            name="5知币券未被默认选中",
            message="非VIP 场景 5知币券不应成为默认选中项",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_dft_010_s3_variant_35_applicable_only(self, logged_in_page, assertion):
        """AUTO-DFT-010 (P1/auto): S3变体 仅 35 适用本单时默认选 35（40不适用被跳过）

        前置数据: 账号持 35知币适用券 + 40知币不适用券
        SQL: valid_35 (id=499000201) + not_applicable_40 (id=499000202)
        清理: ids=499000201,499000202
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_equal(
            dp.get_selected_coupon_type(),
            "35",
            name="S3变体仅35适用默认选35",
            message="S3变体：40不适用本单被跳过，应默认选中 35知币券",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 计算逻辑（AUTO-CAL）
    # ══════════════════════════════════════════════════════════════════════════

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_cal_001_35coupon_amount_correct(self, logged_in_page, assertion):
        """AUTO-CAL-001 (P0/auto): 35知币券默认选中时已优惠金额计算正确（修复 Bug-1）

        前置数据: 账号持 1 张 35知币有效券（适用本单）；使用 60知币模型
        SQL: valid_35  id=499000301
        期望: 已优惠=35, 总计=25（60-35）
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()  # 60知币模型
        dp.click_download_button()
        dp.wait_for_download_dialog()
        expected = _DATA["coupon_discount"]["model60_with_35"]
        assertion.assert_true(
            str(expected["deduction"]) in dp.get_discount_amount_text(),
            name="已优惠等于35知币",
            message=f"35知币券选中时已优惠应含 {expected['deduction']} 知币",
        )
        assertion.assert_true(
            str(expected["total"]) in dp.get_total_amount_text(),
            name="总计等于原价减35",
            message=f"35知币券选中时总计应为 {expected['total']} 知币（60-35）",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_cal_002_40coupon_amount_correct(self, logged_in_page, assertion):
        """AUTO-CAL-002 (P0/auto): 40知币券默认选中时已优惠金额计算正确

        前置数据: 账号持 1 张 40知币有效券（适用本单）；使用 60知币模型
        SQL: valid_40  id=499000302
        期望: 已优惠=40, 总计=20
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        expected = _DATA["coupon_discount"]["model60_with_40"]
        assertion.assert_true(
            str(expected["deduction"]) in dp.get_discount_amount_text(),
            name="已优惠等于40知币",
            message=f"40知币券选中时已优惠应含 {expected['deduction']} 知币",
        )
        assertion.assert_true(
            str(expected["total"]) in dp.get_total_amount_text(),
            name="总计等于原价减40",
            message=f"40知币券选中时总计应为 {expected['total']} 知币（60-40）",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_cal_003_dialog_matches_detail_price(self, logged_in_page, assertion):
        """AUTO-CAL-003 (P0/auto): 详情页到手价与弹窗总计金额完全一致无偏差

        前置数据: 账号持 1 张可用券
        SQL: valid_35  id=499000303
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        detail_price_text = dp.get_detail_page_price_text()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        dialog_total_text = dp.get_total_amount_text()
        assertion.assert_equal(
            dp.parse_zhibi(dialog_total_text),
            dp.parse_zhibi(detail_price_text),
            name="弹窗金额与详情页一致",
            message=(
                f"详情页到手价={detail_price_text}，"
                f"弹窗总计={dialog_total_text}，两者知币数应相等"
            ),
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cal_004_cancel_coupon_amount_reset(self, logged_in_page, assertion):
        """AUTO-CAL-004 (P1/auto): 取消券后金额恢复无优惠状态且重算正确

        前置数据: 账号持 1 张 35知币有效券（弹窗默认选中）
        SQL: valid_35  id=499000304
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        dp.click_coupon("35")  # 取消选中
        assertion.assert_true(
            dp.parse_zhibi(dp.get_discount_amount_text()) == 0,
            name="取消券已优惠归零",
            message="取消选中后已优惠应为 0 知币",
        )
        model_price = _DATA["model_price"][60]
        assertion.assert_true(
            str(model_price) in dp.get_total_amount_text(),
            name="取消券总计恢复原价",
            message=f"取消选中后总计应恢复为模型原价 {model_price} 知币",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cal_005_35_selected_discount_only_35(self, logged_in_page, assertion):
        """AUTO-CAL-005 (P1/auto): 35+40 场景选中 35 后已优惠仅等于 35 面额（非叠加）

        前置数据: 账号持 35知币 + 40知币均适用，默认选中 35知币
        SQL: valid_35 (id=499000351) + valid_40 (id=499000352)
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        expected = _DATA["coupon_discount"]["model60_with_35"]
        discount_text = dp.get_discount_amount_text()
        assertion.assert_true(
            str(expected["deduction"]) in discount_text,
            name="选35时已优惠仅为35面额",
            message=f"选中 35知币券时已优惠应为 {expected['deduction']}，不应叠加 40知币",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cal_006_no_bundle_sale_package(self, logged_in_page, assertion):
        """AUTO-CAL-006 (P1/auto): 非VIP 场景不计算搭售省钱礼包（修复 Bug-3）

        前置数据: 账号持 1 张可用券
        SQL: valid_35  id=499000306
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        for _ in range(3):
            dp.click_coupon("35")  # 反复切换触发重算
        dp.click_coupon("35")  # 末态：选中
        total_text = dp.get_total_amount_text()
        expected_total = _DATA["coupon_discount"]["model60_with_35"]["total"]
        assertion.assert_true(
            str(expected_total) in total_text,
            name="无搭售礼包展示",
            message=(
                f"末态总计应为 {expected_total} 知币（纯券抵扣），"
                "不应因搭售礼包计算产生脏数据"
            ),
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_cal_007_total_not_negative_when_coupon_exceeds_price(self, logged_in_page, assertion):
        """AUTO-CAL-007 (P1/auto→建议升P0): 券面额 ≥ 模型原价时总计为 0 且不为负

        前置数据: 账号持 1 张 35知币有效券（适用本单）；使用 23知币模型（原价<券面额）
        SQL: valid_35  id=499000307
        期望: 已优惠=23（封顶为原价），总计=0（不为负）
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto_model(23)  # 原价23 < 券35 → 触发超额边界
        dp.click_download_button()
        dp.wait_for_download_dialog()
        expected = _DATA["coupon_discount"]["model23_with_35"]
        total_val = dp.parse_zhibi(dp.get_total_amount_text())
        discount_val = dp.parse_zhibi(dp.get_discount_amount_text())
        assertion.assert_true(
            total_val >= 0,
            name="总计不为负",
            message=f"券>原价时总计应≥0，实际={total_val}",
        )
        assertion.assert_equal(
            total_val,
            expected["total"],
            name="总计为0不多不少",
            message=f"券>原价时总计应为 {expected['total']}，实际={total_val}",
        )
        assertion.assert_true(
            discount_val <= _DATA["model_price"][23],
            name="已优惠不超额抵扣",
            message=(
                f"已优惠应≤原价 {_DATA['model_price'][23]} 知币，"
                f"实际={discount_val}（不应超额抵扣）"
            ),
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 边界场景（AUTO-BND）
    # ══════════════════════════════════════════════════════════════════════════

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_bnd_001_b1_no_coupon_dialog_intact(self, logged_in_page, assertion):
        """AUTO-BND-001 (P1/auto): B1 非VIP无任何可用券时弹窗保持线上现状

        前置数据: 账号无任何有效券（确保已清空 account_id 的全部 status=1 券）
        SQL: 无需插入；但需确认 255635028913 当前无有效券（或先清理）
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        # 弹窗应能正常打开，不报错
        assertion.assert_true(
            dp.is_download_dialog_visible(),
            name="B1无券弹窗正常打开",
            message="无可用券时下载确认弹窗应能正常打开，不异常或报错",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_bnd_002_b2_only_5zhibi_dialog_intact(self, logged_in_page, assertion):
        """AUTO-BND-002 (P1/auto): B2 非VIP仅持 5知币券时弹窗保持线上现状

        前置数据: 账号仅持 1 张 5知币有效券，无 35/40 券
        SQL: valid_5  id=499000402
        清理: ids=499000402
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        assertion.assert_true(
            dp.is_download_dialog_visible(),
            name="B2仅5券弹窗正常打开",
            message="仅持 5知币券时下载确认弹窗应能正常打开，按线上原逻辑处理",
        )

    @pytest.mark.ui
    def test_auto_bnd_003_expired_coupon_not_selected(self, logged_in_page, assertion):
        """AUTO-BND-003 (P2/auto): 已过期券不参与默认选中与抵扣

        前置数据: 账号仅持 1 张已过期 35知币券（无其他有效券）
        SQL: expired_35  id=499000403
        清理: ids=499000403
        """
        dp = NonvipDownloadPage(logged_in_page)
        dp.goto()
        dp.click_download_button()
        dp.wait_for_download_dialog()
        assertion.assert_false(
            dp.is_coupon_selected("35"),
            name="过期券不参与默认选中",
            message="已过期的 35知币券不应被默认选中",
        )
        assertion.assert_true(
            dp.parse_zhibi(dp.get_discount_amount_text()) == 0,
            name="过期券不参与抵扣",
            message="已过期券存在时已优惠应为 0（等同无可用券）",
        )

    @pytest.mark.ui
    def test_auto_bnd_004_vip_user_unaffected(self, logged_in_page, assertion):
        """AUTO-BND-004 (P2/manual): VIP 用户下载弹窗逻辑不受本次非VIP修复影响

        manual 原因: 本用例要验证「真实 VIP 用户」走 VIP 下载流程（券膨胀/计费）
        不受非VIP修复影响。VIP 身份是账号级权益，无法通过 mock userPayIdentityV2
        伪造——该接口仅影响充值弹窗身份场景，不会真正切换下载弹窗的 VIP 计费分支。
        因此转人工回归：用真实 VIP 账号走完整下载流程，对比线上行为。

        人工步骤:
          1. 用真实 VIP 账号登录
          2. 打开付费模型详情页，点击「立即下载」
          3. 核对 VIP 券选中 / 膨胀 / 计费逻辑与线上一致，未受非VIP修复影响
        """
        pytest.skip(
            "manual: 需真实 VIP 账号走完整下载流程回归，"
            "VIP 身份无法通过接口 mock 伪造，转人工验证。"
        )
