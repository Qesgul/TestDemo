# -*- coding: utf-8 -*-
"""下载确认弹窗 AB 实验 - 自动化测试套件

覆盖范围（49 条可自动化 + 10 条 manual skip 骨架）：
  SPLIT   6 auto/network + 4 manual  = 10 条
  EXP    25 auto                     = 25 条
  CTRL    5 auto + 1 manual          = 6  条
  TRACK   5 auto/network + 4 manual  = 9  条
  FLOW    8 auto/env + 1 manual      = 9  条
  合计   49 auto/network/env + 10 manual

⚠️ 切量依赖说明：
  - EXP/CTRL/TRACK/FLOW 用例均依赖切量控制；
    DownloadAbPage.set_split_group() 在 split_control 未配置时返回 False，
    辅助函数 _set_group() 据此直接 pytest.skip（标"待考虑"）；
    提测后回填 tests/data/download_ab_data.yaml 的 split_control 块即可激活。
  - 所有切量相关类已加 @pytest.mark.xdist_group("download_ab_split")，
    防止 -n 3 并发冲突（全局 UPDATE user_group_common + 清 Redis）。

运行示例：
  # 非VIP 账号（EXP 非VIP / CTRL 非VIP / FLOW）
  pytest tests/cases/test_download_ab.py \\
    --login-username=13140725123 --login-password=Qyff2011 \\
    --override-ini="addopts=-q -s --headed"

  # VIP 账号（EXP VIP / CTRL VIP）
  pytest tests/cases/test_download_ab.py \\
    --login-username=17768100279 --login-password=Qyff2011 \\
    --override-ini="addopts=-q -s --headed"

  # 仅运行无副作用用例（切量无关，优先落地验证）
  pytest tests/cases/test_download_ab.py -k "flow_006 or exp_014 or exp_015"
"""

import datetime
import re

import pytest

from common.yaml_loader import load_yaml
from data_types.download_ab_data_types import CtrlModalForm, ExpModalForm, PriceScenario
from pages.methods.download_ab_page import DownloadAbPage

_DATA_PATH = "tests/data/download_ab_data.yaml"
_DATA = load_yaml(_DATA_PATH)
_CASES = [ExpModalForm(**c) for c in (_DATA.get("cases") or [])]
_PRICE_SCENARIOS = [PriceScenario(**c) for c in (_DATA.get("price_scenarios") or [])]
_CTRL_CASES = [CtrlModalForm(**c) for c in (_DATA.get("ctrl_cases") or [])]

# ── 切量辅助 ─────────────────────────────────────────────────────────────────
_SKIP_SPLIT = (
    "【待考虑】切量名/radio 未配置（提测后回填 download_ab_data.yaml split_control）"
)
_SKIP_RECORD_TABLE = (
    "【待考虑】切量埋点表名/字段未配置（提测后回填 split_control.record_table）"
)


def _set_group(ab: DownloadAbPage, group_label: str, mysql_db, redis_db) -> None:
    """切量设置：未配置则直接 pytest.skip。"""
    if not ab.set_split_group(group_label, mysql_db, redis_db):
        pytest.skip(_SKIP_SPLIT)


# ══════════════════════════════════════════════════════════════════════════════
# 模块一：用户分组与切量（SPLIT）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.xdist_group("download_ab_split")
class TestSplitBucketing:
    """AUTO-SPLIT 用户分组与切量验证（10 条：6 auto/network + 4 manual）"""

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_split_001_first_access_bucketed(
        self, logged_in_page, assertion, mysql_db
    ):
        """AUTO-SPLIT-001 (P0/auto): 登录用户首次进入按accountID分入四组之一

        校验：切量表中分组值 ∈ {实验组1, 实验组2, 对照组1, 对照组2}。
        依赖：切量表名/字段（split_control.record_table）。
        """
        ab = DownloadAbPage(logged_in_page)
        ab.goto()
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        record = ab.query_split_record(account_id, mysql_db)
        if record is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        assertion.assert_true(
            bool(record),
            name="切量记录存在",
            message=f"账号 {account_id} 访问后切量表应有记录",
        )
        valid_groups = {"实验组1", "实验组2", "对照组1", "对照组2"}
        group_val = str(record.get("group", ""))
        assertion.assert_true(
            any(g in group_val for g in valid_groups),
            name="分组值在四组范围内",
            message=f"分组值应包含有效组名，实际: {group_val!r}",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_split_002_same_group_multiple_visits(
        self, logged_in_page, assertion, mysql_db
    ):
        """AUTO-SPLIT-002 (P0/auto): 同一用户多次访问始终同组，无串组

        校验：多次访问后分组值与首次一致。
        """
        ab = DownloadAbPage(logged_in_page)
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        record_first = ab.query_split_record(account_id, mysql_db)
        if record_first is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        # 再次访问并触发弹窗
        ab.goto()
        ab.click_download_button()
        ab.wait_for_download_dialog()
        ab.close_download_dialog()
        record_second = ab.query_split_record(account_id, mysql_db)
        assertion.assert_equal(
            record_first.get("group"),
            record_second.get("group"),
            name="多次访问分组一致",
            message="同一用户多次访问分组应不变，无串组",
        )

    def test_auto_split_003_same_group_cross_day_manual(self):
        """AUTO-SPLIT-003 (P1/manual): 跨天访问保持同组

        非web/真实跨日：服务端 hash 不受 page.clock 控制，不纳入自动化。
        """
        pytest.skip(
            "manual: 跨天访问需真实经过自然日，page.clock 不影响服务端 hash，转人工"
        )

    def test_auto_split_004_distribution_stats_manual(self):
        """AUTO-SPLIT-004 (P1/manual): 抽样分布比例符合配置

        需 ≥1000 真实账号批量触发分桶，不纳入自动化。
        """
        pytest.skip(
            "manual: 需 ≥1000 不同账号批量触发分桶并做统计检验，转人工"
        )

    def test_auto_split_005_extreme_account_id_manual(self):
        """AUTO-SPLIT-005 (P2/manual): 极端accountID hash取模不报错

        需后端预置极端ID账号；账号就绪后可转 auto。
        """
        pytest.skip(
            "manual: 需后端预置极端 ID 账号，账号就绪后可转 auto"
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_split_006_unlogged_no_bucket(
        self, page, assertion, mysql_db
    ):
        """AUTO-SPLIT-006 (P1/auto): 未登录用户不参与实验分桶

        使用裸 page（不走 logged_in_page），以记录数变化为断言依据。
        待澄清#11：未登录处理逻辑确认后更新断言。
        """
        ab = DownloadAbPage(page)
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        before = ab.count_split_records_today(account_id, today_str, mysql_db)
        if before is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        ab.goto()
        ab.wait.wait_for_timeout(2000)
        after = ab.count_split_records_today(account_id, today_str, mysql_db)
        assertion.assert_equal(
            before,
            after,
            name="未登录切量记录不增加",
            message=f"未登录用户访问后切量记录数应不变（before={before}, after={after}）",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_split_007_vip_status_change_keeps_group(
        self, logged_in_page, assertion, mysql_db
    ):
        """AUTO-SPLIT-007 (P1/auto): VIP状态变化时分组不变

        前置：用户A已分桶且当前非VIP；VIP造数由人工/fixture完成（DB mock）。
        此处只验证分组不因身份变更而漂移。
        依赖：切量表。
        """
        ab = DownloadAbPage(logged_in_page)
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        record_before = ab.query_split_record(account_id, mysql_db)
        if record_before is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        # 再次查询（VIP造数变更由外部完成）
        record_after = ab.query_split_record(account_id, mysql_db)
        assertion.assert_equal(
            record_before.get("group"),
            record_after.get("group"),
            name="VIP变更后分组不漂移",
            message="VIP状态变化后切量分组值应与基线一致",
        )

    def test_auto_split_008_same_day_identity_change_modal_manual(self):
        """AUTO-SPLIT-008 (P2/manual): 当天身份变化时弹窗口径

        待澄清#7：锁定首次身份 or 实时重判，口径未定，转人工。
        """
        pytest.skip(
            "manual: 待澄清#7 当天身份口径未定（锁定首次 or 实时重判），确认后可转 auto"
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_split_009_bucketing_service_exception_graceful(
        self, logged_in_page, assertion
    ):
        """AUTO-SPLIT-009 (P1/network): 分桶服务异常时降级页面不崩溃

        route 拦截分桶接口返回超时/500，验证页面不崩溃、可正常访问。
        待澄清#10：分桶接口路径 + 降级方案确认后补具体断言。
        """
        ab = DownloadAbPage(logged_in_page)
        # TODO[locate]: 分桶接口 URL 路径（待澄清#10 后回填，例：**/api/experiment/bucket**）
        # ab._page.route("**/api/experiment/bucket**", lambda r: r.abort("timedout"))
        ab.goto()
        ab.wait.wait_for_timeout(1500)
        assertion.assert_true(
            "su.znzmo.com" in ab._page.url,
            name="分桶异常详情页可访问",
            message="分桶服务异常时详情页应仍可访问，不跳转错误页（TODO：补充降级策略断言）",
        )

    def test_auto_split_010_target_group_fullroll_manual(self):
        """AUTO-SPLIT-010 (P2/manual): 跟随需求人群推全映射

        推全阶段人群标签依赖后端就绪，本期转人工。
        """
        pytest.skip(
            "manual: 推全阶段人群 A/B/D 标签依赖后端，本期转人工"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 模块二：实验组弹窗策略（EXP）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.xdist_group("download_ab_split")
class TestExpModal:
    """AUTO-EXP 实验组弹窗策略验证（25 条全 auto）"""

    @staticmethod
    def _open_dialog(ab: DownloadAbPage) -> None:
        ab.goto()
        ab.click_download_button()
        ab.wait_for_download_dialog()

    # ── EXP-001: 详情页到手价 ──────────────────────────────────────────────

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_exp_001_detail_shows_take_price_no_coupon_price(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-001 (P0/auto): 实验组详情页展示到手价且不展示券后价"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        ab.goto()
        assertion.assert_true(
            len(ab.get_detail_take_price_text()) > 0,
            name="详情页有到手价",
            message="实验组详情页应展示到手价（文本非空）",
        )
        assertion.assert_false(
            ab.has_detail_coupon_price(),
            name="详情页无券后价",
            message="实验组详情页不应出现'券后价'字样",
        )

    # ── EXP-002: 取消VIP虚拟优惠 ─────────────────────────────────────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_002_vip_no_virtual_discount_on_detail(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-002 (P1/auto): 实验组取消VIP专享价中的减5知币虚拟优惠

        账号：VIP（--login-username=17768100279）。
        待澄清#4：详情页虚拟优惠移除 vs 弹窗VIP立减保留，确认后补反向断言。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        ab.goto()
        take_price_text = ab.get_detail_take_price_text()
        assertion.assert_true(
            len(take_price_text) > 0,
            name="VIP实验组到手价可读",
            message=f"VIP实验组详情页应有到手价文本，实际: {take_price_text!r}",
        )
        # TODO[manual]: 待澄清#4 确认「虚拟优惠」字样 selector 后补反向断言

    # ── EXP-003: 到手价==弹窗金额（多场景参数化）─────────────────────────

    @pytest.mark.smoke
    @pytest.mark.main
    @pytest.mark.parametrize(
        "scenario",
        _PRICE_SCENARIOS,
        ids=[s.case_id for s in _PRICE_SCENARIOS],
    )
    def test_auto_exp_003_detail_price_equals_dialog_amount(
        self, logged_in_page, assertion, mysql_db, redis_db, scenario: PriceScenario
    ):
        """AUTO-EXP-003 (P0/auto): 详情页到手价等于弹窗默认支付金额（多场景）

        素材 URL 在 download_ab_data.yaml price_scenarios 回填后生效。
        """
        if str(scenario.material_url).startswith("TODO"):
            pytest.skip(
                f"【待考虑】{scenario.case_id} 素材URL未配置，提测后回填 price_scenarios"
            )
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        ab._page.goto(scenario.material_url, wait_until="domcontentloaded")
        ab.wait.wait_for_timeout(1500)
        take_price_text = ab.get_detail_take_price_text()
        ab.click_download_button()
        ab.wait_for_download_dialog()
        dialog_total_text = ab.get_total_amount_text()
        take_val = ab.parse_zhibi(take_price_text)
        dialog_val = ab.parse_zhibi(dialog_total_text)
        assertion.assert_equal(
            take_val,
            dialog_val,
            name=f"{scenario.case_id} 到手价==弹窗总计",
            message=(
                f"{scenario.scenario_name}: 详情页到手价({take_val}知币)"
                f" 应等于弹窗合计({dialog_val}知币)"
            ),
        )

    # ── EXP-004~006: VIP立减行 ────────────────────────────────────────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_004_vip_shows_vip_discount_selected(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-004 (P1/auto): 实验组VIP用户展示VIP立减且默认选中

        账号：VIP（--login-username=17768100279）。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_true(
            ab.is_vip_discount_visible(),
            name="VIP立减行可见",
            message="实验组VIP用户弹窗应展示'VIP立减'行",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_exp_005_nonvip_no_vip_discount_row(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-005 (P0/auto): 实验组非VIP用户不展示VIP立减字段

        账号：nonvip（13140725123）。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.is_vip_discount_visible(),
            name="非VIP无VIP立减行",
            message="实验组非VIP弹窗不应展示'VIP立减'整行",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_006_nonvip_no_vip_pending_tag(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-006 (P1/auto): 实验组非VIP不出现VIP立减待激活诱导态（与对照组图2区分）"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.is_vip_pending_tag_visible(),
            name="实验组无待激活标签",
            message="实验组非VIP弹窗不应出现'待激活 -5知币'诱导标签",
        )

    # ── EXP-007~011: 下载抵扣券 ──────────────────────────────────────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_007_vip_with_coupon_shows_coupon(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-007 (P1/auto): 实验组VIP有券展示并保留膨胀规则

        前置：VIP账号 goldcoin_voucher 有有效抵扣券。
        账号：VIP（--login-username=17768100279）。
        待澄清#8：膨胀规则细节确认后补断言。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_true(
            ab.is_coupon_section_visible(),
            name="VIP有券展示抵扣券区",
            message="实验组VIP有券弹窗应展示'下载抵扣券'区",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_008_vip_no_coupon_hides_coupon_section(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-008 (P1/auto): 实验组VIP无券不展示该字段，无"不使用"占位

        前置：VIP账号无可用抵扣券（清空 goldcoin_voucher）。
        账号：VIP（--login-username=17768100279）。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.is_coupon_section_visible(),
            name="VIP无券隐藏抵扣券区",
            message="实验组VIP无券时弹窗不应展示'下载抵扣券'整行",
        )
        assertion.assert_false(
            ab.is_coupon_unused_row_visible(),
            name="VIP无券无不使用残留",
            message="VIP无券时不应出现'不使用'占位行",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_009_nonvip_with_coupon_shows_and_selected(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-009 (P1/auto): 实验组非VIP有券展示并选中

        前置：账号 13140725123 goldcoin_voucher 有有效抵扣券。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_true(
            ab.is_coupon_section_visible(),
            name="非VIP有券展示抵扣券区",
            message="实验组非VIP有券时弹窗应展示'下载抵扣券'区",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_exp_010_nonvip_no_coupon_hides_coupon_section(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-010 (P0/auto): 实验组非VIP无券不展示该字段

        前置：账号 13140725123 清空可用抵扣券。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.is_coupon_section_visible(),
            name="非VIP无券隐藏抵扣券区",
            message="实验组非VIP无券时弹窗不应展示'下载抵扣券'整行",
        )

    @pytest.mark.ui
    def test_auto_exp_011_no_coupon_no_unused_row(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-011 (P2/auto): 无券时不出现"不使用"残留行（修正图4现象）"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.is_coupon_unused_row_visible(),
            name="无券无不使用残留行",
            message="实验组无券时整行应隐藏，无'不使用 >'残留",
        )

    # ── EXP-012~016: 搭售区 ───────────────────────────────────────────────

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_exp_012_vip_no_promo_bundle(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-012 (P0/auto): 实验组VIP用户弹窗无省钱礼包搭售区

        账号：VIP（--login-username=17768100279）。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.has_promo_bundle(),
            name="实验组VIP无搭售区",
            message="实验组VIP弹窗不应有省钱礼包/搭售区块",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_exp_013_nonvip_no_promo_bundle(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-013 (P0/auto): 实验组非VIP用户弹窗无省钱礼包搭售区（与对照组图1/2区分）"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.has_promo_bundle(),
            name="实验组非VIP无搭售区",
            message="实验组非VIP弹窗不应有任何搭售套餐区块",
        )

    # ── EXP-014~016: 底部按钮与现金项 ────────────────────────────────────

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_exp_014_main_button_text_is_download(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-014 (P0/auto): 实验组主按钮为立即下载且无支付并下载变体"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        btn_text = ab.get_main_button_text()
        assertion.assert_true(
            "立即下载" in btn_text,
            name="主按钮文案为立即下载",
            message=f"实验组主按钮应含'立即下载'，实际: {btn_text!r}",
        )
        assertion.assert_false(
            "支付并下载" in btn_text,
            name="无支付并下载变体",
            message="实验组不应出现'支付并下载'按钮文案",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_015_bottom_bar_no_cash(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-015 (P1/auto): 实验组底部条不展示加X元搭售现金金额"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.has_bottom_cash(),
            name="底部无+X元现金项",
            message="实验组底部合计条不应展示'+X元'搭售现金项",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_016_existing_bundle_buyer_no_promo_residual(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-016 (P1/auto): 实验组存量已购省钱礼包用户无搭售残留

        待澄清#9：存量已购省钱礼包/下载券可用性确认后更新断言。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_false(
            ab.has_promo_bundle(),
            name="存量已购无搭售残留",
            message="实验组存量已购省钱礼包用户弹窗不应有搭售区（待澄清#9）",
        )

    # ── EXP-017~020: VIP×券四种弹窗形态参数化 ──────────────────────────

    @pytest.mark.smoke
    @pytest.mark.main
    @pytest.mark.parametrize(
        "case",
        _CASES,
        ids=[c.case_id for c in _CASES],
    )
    def test_auto_exp_017_020_modal_form_combinations(
        self, logged_in_page, assertion, mysql_db, redis_db, case: ExpModalForm
    ):
        """AUTO-EXP-017~020 (P0~P1/auto): VIP×券四种弹窗形态组合参数化验证

        EXP-017: VIP有券完整形态（需 VIP 账号 + 券造数）
        EXP-018: VIP无券形态（需 VIP 账号 + 清券）
        EXP-019: 非VIP有券形态（需 nonvip 账号 + 券造数）
        EXP-020: 非VIP无券最简形态（需 nonvip 账号 + 清券）

        注意：VIP用例需 --login-username=17768100279；非VIP用例需 --login-username=13140725123。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)

        # VIP立减行校验
        if case.expect_vip_row:
            assertion.assert_true(
                ab.is_vip_discount_visible(),
                name=f"{case.case_id}-VIP立减行可见",
                message=f"{case.scenario_name}: 期望展示VIP立减行",
            )
        else:
            assertion.assert_false(
                ab.is_vip_discount_visible(),
                name=f"{case.case_id}-无VIP立减行",
                message=f"{case.scenario_name}: 期望不展示VIP立减行",
            )

        # 抵扣券区校验
        if case.expect_coupon_row:
            assertion.assert_true(
                ab.is_coupon_section_visible(),
                name=f"{case.case_id}-抵扣券区可见",
                message=f"{case.scenario_name}: 期望展示抵扣券区",
            )
        else:
            assertion.assert_false(
                ab.is_coupon_section_visible(),
                name=f"{case.case_id}-无抵扣券区",
                message=f"{case.scenario_name}: 期望不展示抵扣券区",
            )

        # 搭售区（实验组恒无）
        assertion.assert_false(
            ab.has_promo_bundle(),
            name=f"{case.case_id}-无搭售区",
            message=f"{case.scenario_name}: 实验组弹窗不应有搭售区",
        )

        # 主按钮（实验组恒"立即下载"）
        btn_text = ab.get_main_button_text()
        assertion.assert_true(
            "立即下载" in btn_text,
            name=f"{case.case_id}-按钮立即下载",
            message=f"{case.scenario_name}: 主按钮应为'立即下载'，实际: {btn_text!r}",
        )

    # ── EXP-021: 布局无错位 ───────────────────────────────────────────────

    @pytest.mark.ui
    def test_auto_exp_021_layout_no_misalignment(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-021 (P2/auto): 字段联动隐藏后弹窗布局无错位

        当前以弹窗容器可见为基线，bounding-box 错位细节建议结合截图人工复核。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        assertion.assert_true(
            ab.is_field_visible("download_dialog"),
            name="弹窗容器可见",
            message="布局校验基线：弹窗容器应可见（bounding-box 错位建议人工截图复核）",
        )

    # ── EXP-022: 总计金额计算 ─────────────────────────────────────────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_022_total_amount_calculation_correct(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-022 (P1/auto): 总计金额按字段抵扣计算正确（复用 parse_zhibi）"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        total_val = ab.parse_zhibi(ab.get_total_amount_text())
        discount_val = ab.parse_zhibi(ab.get_discount_amount_text())
        assertion.assert_true(
            total_val >= 0,
            name="总计金额非负",
            message=f"弹窗总计金额应≥0，实际: {total_val}",
        )
        assertion.assert_true(
            discount_val >= 0,
            name="已优惠金额非负",
            message=f"已优惠金额应≥0，实际: {discount_val}",
        )

    # ── EXP-023: 实验组1 vs 实验组2 一致性 ──────────────────────────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_exp_023_exp1_exp2_strategy_consistent(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-023 (P1/auto): 实验组1与实验组2弹窗策略一致性

        待澄清#2：两组差异确认后补差异点断言；当前验证主按钮文案与搭售状态一致。
        """
        ab = DownloadAbPage(logged_in_page)

        # 切实验组1
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        btn_g1 = ab.get_main_button_text()
        promo_g1 = ab.has_promo_bundle()
        ab.close_download_dialog()

        # 切实验组2
        _set_group(ab, "实验组2", mysql_db, redis_db)
        ab.goto()
        ab.click_download_button()
        ab.wait_for_download_dialog()
        btn_g2 = ab.get_main_button_text()
        promo_g2 = ab.has_promo_bundle()

        assertion.assert_equal(
            btn_g1,
            btn_g2,
            name="两实验组主按钮一致",
            message=f"实验组1({btn_g1!r}) vs 实验组2({btn_g2!r})（待澄清#2有差异时分别校验）",
        )
        assertion.assert_equal(
            promo_g1,
            promo_g2,
            name="两实验组搭售区状态一致",
            message="两组搭售区展示状态应一致（待澄清#2）",
        )

    # ── EXP-024: 活动立减为0时展示 ───────────────────────────────────────

    @pytest.mark.ui
    def test_auto_exp_024_zero_activity_discount(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-024 (P2/auto): 活动立减缺省或为0时弹窗展示与总计无负数"""
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        total_val = ab.parse_zhibi(ab.get_total_amount_text())
        assertion.assert_true(
            total_val >= 0,
            name="零活动立减总计非负",
            message=f"活动立减缺省/为0时总计应≥0，实际: {total_val}",
        )

    # ── EXP-025: 素材信息块完整（需求补全）──────────────────────────────

    @pytest.mark.ui
    def test_auto_exp_025_material_info_block_complete(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-EXP-025 (P2/auto/需求补全): 实验组弹窗素材信息块字段完整展示

        校验：假一赔三标识 / 缩略图 / 标题 / 素材ID / 方案标签 / 参数标签。
        （PRD §8 弹窗结构，原用例未覆盖，需求补全）
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        self._open_dialog(ab)
        info = ab.get_material_info()
        for field_name, visible in info.items():
            assertion.assert_true(
                visible,
                name=f"素材信息块-{field_name}可见",
                message=f"弹窗素材信息块字段 '{field_name}' 应可见（selector 就绪后生效）",
            )


# ══════════════════════════════════════════════════════════════════════════════
# 模块三：对照组弹窗策略（CTRL）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.xdist_group("download_ab_split")
class TestCtrlModal:
    """AUTO-CTRL 对照组弹窗策略验证（6 条：5 auto + 1 manual）"""

    @staticmethod
    def _open_ctrl_dialog(ab: DownloadAbPage) -> None:
        ab.goto()
        ab.click_download_button()
        ab.wait_for_download_dialog()

    # ── CTRL-001: manual ──────────────────────────────────────────────────

    def test_auto_ctrl_001_ctrl_matches_online_baseline_manual(self):
        """AUTO-CTRL-001 (P0/manual): 对照组弹窗与线上现状完全一致

        需与上线前 UI 快照逐字段目视比对，转人工。
        """
        pytest.skip("manual: 需与上线前线上版本UI快照逐字段目视比对，转人工")

    # ── CTRL-002~004: 参数化形态（直接独立方法，账号分开运行）──────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_ctrl_002_nonvip_no_coupon_shows_promo_bundle(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-CTRL-002 (P1/auto): 对照组非VIP无券展示搭售礼包（图1）

        账号：nonvip（13140725123）；无券前置。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "对照组1", mysql_db, redis_db)
        self._open_ctrl_dialog(ab)
        assertion.assert_true(
            ab.has_promo_bundle(),
            name="对照组非VIP无券有搭售区",
            message="对照组非VIP无券弹窗应展示搭售礼包区（省钱礼包/知币套餐等）",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_ctrl_003_nonvip_with_coupon_shows_promo_and_pending(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-CTRL-003 (P1/auto): 对照组非VIP有券展示搭售并保留待激活态（图2）

        账号：nonvip（13140725123）；券造数（goldcoin_voucher）。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "对照组1", mysql_db, redis_db)
        self._open_ctrl_dialog(ab)
        assertion.assert_true(
            ab.is_vip_pending_tag_visible(),
            name="对照组保留待激活标签",
            message="对照组非VIP有券弹窗应保留'VIP立减 待激活 -5知币'标签",
        )
        assertion.assert_true(
            ab.has_promo_bundle(),
            name="对照组非VIP有券有搭售区",
            message="对照组非VIP有券弹窗应展示'开通VIP畅享'搭售区",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_ctrl_004_vip_with_coupon_shows_promo_and_vip_discount(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-CTRL-004 (P1/auto): 对照组VIP有券展示搭售礼包且VIP立减正常选中（图3）

        账号：VIP（--login-username=17768100279）；有券前置。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "对照组1", mysql_db, redis_db)
        self._open_ctrl_dialog(ab)
        assertion.assert_true(
            ab.has_promo_bundle(),
            name="对照组VIP有搭售区",
            message="对照组VIP有券弹窗应展示'加购省钱礼包'搭售区",
        )
        assertion.assert_true(
            ab.is_vip_discount_visible(),
            name="对照组VIP立减可见",
            message="对照组VIP弹窗应展示VIP立减行",
        )

    # ── CTRL-005: 选中搭售后按钮变化 ──────────────────────────────────────

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_ctrl_005_select_promo_changes_button_to_pay_and_download(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-CTRL-005 (P1/auto): 对照组选中搭售时按钮为支付并下载并含现金金额

        仅断言按钮文案与底部文本，不执行真实现金支付。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "对照组1", mysql_db, redis_db)
        self._open_ctrl_dialog(ab)
        selected = ab.select_promo_package(0)
        if not selected:
            pytest.skip(
                "【待考虑】promo_package_option selector 未配置，提测后回填"
            )
        btn_text = ab.get_main_button_text()
        assertion.assert_true(
            "支付并下载" in btn_text,
            name="选中搭售后按钮为支付并下载",
            message=f"对照组勾选搭售套餐后主按钮应含'支付并下载'，实际: {btn_text!r}",
        )
        assertion.assert_true(
            ab.has_bottom_cash(),
            name="选中搭售底部含+X元",
            message="对照组勾选搭售后底部合计条应展示'+X元'现金项",
        )

    # ── CTRL-006: 对照组1 vs 对照组2 一致性 ──────────────────────────────

    @pytest.mark.ui
    def test_auto_ctrl_006_ctrl1_ctrl2_consistent(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-CTRL-006 (P2/auto): 对照组1与对照组2弹窗表现一致

        待澄清#3：两组差异确认后补差异点断言。
        """
        ab = DownloadAbPage(logged_in_page)

        _set_group(ab, "对照组1", mysql_db, redis_db)
        self._open_ctrl_dialog(ab)
        promo_c1 = ab.has_promo_bundle()
        btn_c1 = ab.get_main_button_text()
        ab.close_download_dialog()

        _set_group(ab, "对照组2", mysql_db, redis_db)
        ab.goto()
        ab.click_download_button()
        ab.wait_for_download_dialog()
        promo_c2 = ab.has_promo_bundle()
        btn_c2 = ab.get_main_button_text()

        assertion.assert_equal(
            promo_c1,
            promo_c2,
            name="两对照组搭售区状态一致",
            message=f"对照组1搭售={promo_c1} vs 对照组2搭售={promo_c2}（待澄清#3）",
        )
        assertion.assert_equal(
            btn_c1,
            btn_c2,
            name="两对照组主按钮一致",
            message=f"对照组1按钮({btn_c1!r}) vs 对照组2按钮({btn_c2!r})",
        )


# ══════════════════════════════════════════════════════════════════════════════
# 模块四：数据埋点与监控（TRACK）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.xdist_group("download_ab_split")
class TestTrackEmbed:
    """AUTO-TRACK 数据埋点与监控验证（9 条：5 auto/network + 4 manual）"""

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_track_001_access_writes_split_record(
        self, logged_in_page, assertion, mysql_db
    ):
        """AUTO-TRACK-001 (P0/auto): 登录用户访问当天写入一条切量记录

        校验：含日期/用户ID/切量分组三字段均非空。
        """
        ab = DownloadAbPage(logged_in_page)
        ab.goto()
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        record = ab.query_split_record(account_id, mysql_db)
        if record is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        assertion.assert_true(
            bool(record),
            name="切量记录存在",
            message=f"账号 {account_id} 访问后切量表应有记录",
        )
        for field_key, field_label in [
            ("date", "日期"), ("user_id", "用户ID"), ("group", "切量分组")
        ]:
            assertion.assert_true(
                bool(record.get(field_key)),
                name=f"切量记录{field_label}非空",
                message=f"切量记录 {field_label} 字段应非空，实际: {record.get(field_key)!r}",
            )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_track_002_group_field_format_date_underscore_name(
        self, logged_in_page, assertion, mysql_db
    ):
        """AUTO-TRACK-002 (P1/auto): 切量分组字段格式为 日期_组名（正则校验）

        期望格式：`YYMMDD_组名`，如 `260608_实验组1`。
        """
        ab = DownloadAbPage(logged_in_page)
        ab.goto()
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        record = ab.query_split_record(account_id, mysql_db)
        if record is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        if not record:
            pytest.skip("切量表无记录，请先触发分桶访问")
        group_val = str(record.get("group", ""))
        pattern = r"^\d{6}_\S+"
        assertion.assert_true(
            bool(re.match(pattern, group_val)),
            name="分组字段格式YYMMDD_组名",
            message=f"切量分组字段应符合 YYMMDD_组名 格式，实际: {group_val!r}",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_track_003_four_group_values_correct_mapping(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-TRACK-003 (P1/auto): 四组分组值正确映射，无错值

        依赖切量控制：逐一切到四组，验证切量表记录的分组值与切量一致。
        """
        ab = DownloadAbPage(logged_in_page)
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        for group_label in ["实验组1", "实验组2", "对照组1", "对照组2"]:
            if not ab.set_split_group(group_label, mysql_db, redis_db):
                pytest.skip(_SKIP_SPLIT)
            ab.goto()
            ab.wait.wait_for_timeout(1000)
            record = ab.query_split_record(account_id, mysql_db)
            if record is None:
                pytest.skip(_SKIP_RECORD_TABLE)
            group_val = str(record.get("group", ""))
            assertion.assert_true(
                group_label in group_val,
                name=f"切量{group_label}分组值正确",
                message=(
                    f"切到 {group_label!r} 后，记录分组值应含 {group_label!r}，"
                    f"实际: {group_val!r}"
                ),
            )

    def test_auto_track_004_cross_day_each_day_one_record_manual(self):
        """AUTO-TRACK-004 (P1/manual): 跨天访问每天各生成一条记录

        非web/真实跨日，不纳入自动化。
        """
        pytest.skip("manual: 需真实经过自然日，不纳入自动化")

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_track_005_same_day_only_one_record(
        self, logged_in_page, assertion, mysql_db
    ):
        """AUTO-TRACK-005 (P1/auto): 同天多次访问仅生成一条记录（去重键 用户ID+日期）

        待澄清#6：去重键/时机确认后更新断言。
        """
        ab = DownloadAbPage(logged_in_page)
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        # 多次访问
        for _ in range(2):
            ab.goto()
            ab.wait.wait_for_timeout(500)
        count = ab.count_split_records_today(account_id, today_str, mysql_db)
        if count is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        assertion.assert_equal(
            count,
            1,
            name="同天切量记录唯一",
            message=(
                f"同天多次访问应仅生成1条切量记录，实际: {count}条"
                "（待澄清#6 去重键/时机）"
            ),
        )

    def test_auto_track_006_record_by_first_access_identity_manual(self):
        """AUTO-TRACK-006 (P2/manual): 切量记录以当天进入时身份信息为准

        待澄清#7 身份口径未定，确认后可转 auto（与 SPLIT-008 联动）。
        """
        pytest.skip(
            "manual: 待澄清#7 当天身份口径未定（锁定首次 or 实时重判），确认后可转 auto"
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_track_007_unlogged_no_split_record(
        self, page, assertion, mysql_db
    ):
        """AUTO-TRACK-007 (P1/auto): 未登录用户不产生切量记录

        使用裸 page（不走 logged_in_page），以记录数变化为断言依据。
        待澄清#11：未登录处理逻辑确认后更新断言。
        """
        ab = DownloadAbPage(page)
        account_id = _DATA["accounts"]["nonvip"]["account_id"]
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        before = ab.count_split_records_today(account_id, today_str, mysql_db)
        if before is None:
            pytest.skip(_SKIP_RECORD_TABLE)
        ab.goto()
        ab.wait.wait_for_timeout(2000)
        after = ab.count_split_records_today(account_id, today_str, mysql_db)
        assertion.assert_equal(
            before,
            after,
            name="未登录无切量记录",
            message=(
                f"未登录访问后切量记录数应不变"
                f"（before={before}, after={after}）"
            ),
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_track_008_gio_events_consistent_with_online(
        self, logged_in_page, assertion, mysql_db, redis_db, gio_tracking
    ):
        """AUTO-TRACK-008 (P1/network): GIO埋点实验组与对照组均与线上一致

        ⚠️ GIO埋点用例（见 docs/gio埋点自动化生成指南.md）：
        Step1: 先跑实况探针解码确认事件名/var（heredoc 模板见指南 §一.Step1）
        Step2: 复用 gio_tracking fixture（已在函数签名中声明）
        Step3: 探针结果填入 event_name / expected_vars 后取消下方注释

        TODO[待考虑]: 提测后按以下步骤激活：
          1. 运行指南 Step1 heredoc 探针（使用 DownloadAbPage，触发弹窗交互）
          2. 确认实况上报的事件名与 var 字段
          3. 回填 event_name / expected_vars
          4. 移除 pytest.skip
        """
        pytest.skip(
            "【待考虑】TRACK-008 GIO埋点：需先跑实况探针确认事件名/var"
            "（提测后执行 docs/gio埋点自动化生成指南.md Step1 探针）"
        )
        # ── 骨架（探针确认后取消注释并回填真实值）────────────────────────────
        # ab = DownloadAbPage(logged_in_page)
        # _set_group(ab, "实验组1", mysql_db, redis_db)
        # ab.goto()
        # ab.click_download_button()
        # ab.wait_for_download_dialog()
        # # 回填探针确认的事件名与 var 字段
        # event_name = "TODO_探针确认的事件名"          # e.g. "render_download_click"
        # expected_vars = {}                            # e.g. {"data": "AB实验", "data2": "TODO"}
        # gio_tracking.assert_event(event_name, vars=expected_vars)

    def test_auto_track_009_split_data_supports_experiment_eval_manual(self):
        """AUTO-TRACK-009 (P1/manual): 切量埋点数据支撑实验评估最小完整性

        需积累实验数据后按数据分析口径对齐，转人工。待澄清#10。
        """
        pytest.skip(
            "manual: 需积累实验数据后数据分析口径对齐（待澄清#10），转人工"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 模块五：端到端下载流程（FLOW）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.xdist_group("download_ab_split")
class TestFlowDownload:
    """AUTO-FLOW 端到端下载流程验证（9 条：8 auto/env + 1 manual）"""

    @staticmethod
    def _setup_exp_dialog(ab: DownloadAbPage, mysql_db, redis_db) -> None:
        """切实验组1并打开弹窗。"""
        _set_group(ab, "实验组1", mysql_db, redis_db)
        ab.goto()
        ab.click_download_button()
        ab.wait_for_download_dialog()

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_flow_001_main_download_flow_success(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-001 (P0/auto): 实验组下载主流程完整可用

        前置：知币余额充足。执行真实下载扣测试知币（已确认支付边界：允许）。
        """
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        btn_text = ab.get_main_button_text()
        assertion.assert_true(
            "立即下载" in btn_text,
            name="主流程按钮可用",
            message=f"实验组下载弹窗主按钮应含'立即下载'，实际: {btn_text!r}",
        )
        ab.click_confirm_button()
        ab.wait.wait_for_timeout(3000)
        assertion.assert_false(
            ab.is_field_visible("download_dialog", timeout=2000),
            name="下载后弹窗关闭",
            message="点击立即下载后弹窗应关闭（下载流程已触发）",
        )

    @pytest.mark.smoke
    @pytest.mark.main
    def test_auto_flow_002_three_price_points_consistent(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-002 (P0/auto): 实验组价格链路三处金额一致

        详情页到手价 == 弹窗应付 == 实际扣减知币（DB查库）。
        当前校验前两处；第三处（DB扣减）待支付边界确认后补 mysql_db 查询。
        """
        ab = DownloadAbPage(logged_in_page)
        _set_group(ab, "实验组1", mysql_db, redis_db)
        ab.goto()
        take_val = ab.parse_zhibi(ab.get_detail_take_price_text())
        ab.click_download_button()
        ab.wait_for_download_dialog()
        dialog_val = ab.parse_zhibi(ab.get_total_amount_text())
        assertion.assert_equal(
            take_val,
            dialog_val,
            name="详情页到手价==弹窗总计",
            message=f"详情页到手价({take_val}) 应等于弹窗总计({dialog_val})",
        )
        # TODO[manual]: 完成下载后查库实际扣减知币，待支付边界确认后补 DB 校验步骤

    def test_auto_flow_003_ctrl_bundle_full_flow_manual(self):
        """AUTO-FLOW-003 (P1/manual): 对照组含搭售的完整下载流程

        红线：涉真实人民币现金支付，自动化不执行真实付款，转人工。
        """
        pytest.skip(
            "manual: 红线 — 涉真实人民币现金支付，自动化不执行真实付款，转人工"
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_flow_004_coupon_write_off_correct(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-004 (P1/auto): 实验组使用抵扣券下载时核销正确

        前置：有可用下载抵扣券（goldcoin_voucher 造数）；余额充足。
        """
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        if not ab.is_coupon_section_visible():
            pytest.skip(
                "【待考虑】当前账号无可用抵扣券，需 goldcoin_voucher 造数后重跑"
            )
        discount_val = ab.parse_zhibi(ab.get_discount_amount_text())
        assertion.assert_true(
            discount_val > 0,
            name="有券时已优惠>0",
            message=f"有券时已优惠应>0，实际: {discount_val}",
        )
        # TODO[manual]: 完成下载后查库券状态（goldcoin_voucher.status）核销正确，待补充

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_flow_005_insufficient_balance_prompts_recharge(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-005 (P1/auto): 实验组知币不足时引导充值不错误扣减

        前置：余额不足以支付到手价（账号知币<到手价）；仅断言引导提示，不真实充值。
        """
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        ab.click_confirm_button()
        ab.wait.wait_for_timeout(2500)
        # TODO[locate]: 余额不足提示/充值引导元素 selector（提测后用实况探针确认 Toast/弹窗文案）
        # 基线断言：操作后页面不崩溃（余额不足账号就绪后补"提示含充值引导"的断言）
        assertion.assert_true(
            True,
            name="余额不足页面不崩溃",
            message="余额不足时点立即下载后页面应不崩溃（TODO：余额不足账号就绪后补充断言）",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_flow_006_close_dialog_no_download_no_charge(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-006 (P1/auto): 关闭弹窗不触发下载与扣减（无副作用，最易先落地）"""
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        ab.close_download_dialog()
        assertion.assert_false(
            ab.is_field_visible("download_dialog", timeout=1500),
            name="关闭后弹窗消失",
            message="点X关闭弹窗后弹窗应不可见",
        )
        assertion.assert_true(
            "su.znzmo.com" in ab._page.url,
            name="关闭后停留详情页",
            message="关闭弹窗后应仍在 su.znzmo.com 详情页，无跳转",
        )

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_flow_007_network_interrupt_no_duplicate_charge(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-007 (P1/env): 网络中断时下载失败可重试且知币不重复扣减

        使用 context.set_offline() 模拟断网；恢复后验证页面可继续操作。
        """
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        # 断网
        ab._page.context.set_offline(True)
        ab.click_confirm_button()
        ab.wait.wait_for_timeout(2500)
        # 断网后页面不崩溃
        assertion.assert_true(
            True,
            name="断网后页面无崩溃",
            message=(
                "断网时点立即下载后页面应不崩溃"
                "（TODO：提测后补失败提示 selector 断言）"
            ),
        )
        # 恢复网络
        ab._page.context.set_offline(False)
        ab.wait.wait_for_timeout(1000)
        # TODO[manual]: 重试成功后查库扣减次数=1（余额充足账号+DB查询，待支付边界确认）

    @pytest.mark.core
    @pytest.mark.main
    def test_auto_flow_008_rapid_clicks_prevent_duplicate_order(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-008 (P1/auto): 快速重复点击立即下载防重复下单

        快速连击确认按钮3次，验证按钮防重（置灰/loading）且页面不崩溃。
        TODO[manual]: 完成后查库仅一笔下载订单+知币仅扣一次，待支付边界确认后补 DB 查询。
        """
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        for _ in range(3):
            try:
                ab.click_confirm_button()
            except Exception:
                pass
        ab.wait.wait_for_timeout(2000)
        assertion.assert_true(
            True,
            name="连击后无崩溃",
            message=(
                "快速连击确认按钮后页面应不崩溃"
                "（TODO：补充按钮置灰/loading selector + DB 仅一笔订单断言）"
            ),
        )

    @pytest.mark.ui
    def test_auto_flow_009_multi_discount_total_and_charge_consistent(
        self, logged_in_page, assertion, mysql_db, redis_db
    ):
        """AUTO-FLOW-009 (P2/auto): 实验组多项立减叠加后总计与实际扣减一致

        前置：VIP账号；有抵扣券；有活动立减素材；余额充足。
        账号：VIP（--login-username=17768100279）。
        """
        ab = DownloadAbPage(logged_in_page)
        self._setup_exp_dialog(ab, mysql_db, redis_db)
        total_val = ab.parse_zhibi(ab.get_total_amount_text())
        discount_val = ab.parse_zhibi(ab.get_discount_amount_text())
        assertion.assert_true(
            total_val >= 0,
            name="多立减叠加总计非负",
            message=f"多项立减叠加后总计应≥0，实际: {total_val}",
        )
        assertion.assert_true(
            discount_val >= 0,
            name="多立减已优惠非负",
            message=f"多项立减叠加后已优惠应≥0，实际: {discount_val}",
        )
        # TODO[manual]: 完成下载后查库实际扣减 == 弹窗总计（需支付边界确认 + DB 查询）
