"""
充值弹窗测试用例 - 实现充值弹窗信息获取流程

流程：
1. Cookie登录
2. 跳转至指定URL
3. 依次点击充值按钮和下载充值按钮
4. 拦截接口并mock data字段为1-14
5. 获取并记录对应充值弹窗信息
"""
import pytest

from data_types.test_data_types import LoginCaseData
from pages.methods.login_page import LoginPage
from pages.methods.model_detail_page import ModelDetailPage
from tests.steps.test_base import load_typed_cases_from_yaml, case_ids


LOGIN_CASES = load_typed_cases_from_yaml("tests/data/recharge_flow_data.yaml", LoginCaseData)
LOGIN_CASE_IDS = case_ids(LOGIN_CASES)

if not LOGIN_CASES:
    pytest.skip("未匹配到可执行数据，请检查 settings.yaml 中 execution.tags 过滤条件", allow_module_level=True)


class TestRechargeFlow:
    """充值弹窗测试类"""

    TARGET_URL = "https://3d.znzmo.com/3dmoxing/1198790555.html?requestId=22a843f6-3354-4146-a7b2-23f5c56a2d3d"
    API_URL = "https://api.znzmo.com/payCenter/pay/userPayIdentityV2"

    @pytest.mark.parametrize("case_data", LOGIN_CASES, ids=LOGIN_CASE_IDS)
    @pytest.mark.core
    @pytest.mark.ui
    @pytest.mark.popup
    def test_recharge_modal_info_with_mock(self, case_data, page):
        """
        充值弹窗信息获取测试用例 - 带接口mock

        执行流程：
        1. 使用Cookie登录（无Cookie则走正常登录）
        2. 跳转至指定3D模型详情页
        3. 对data=1-14依次进行测试
        4. 对每个data值：
           a. mock接口返回值
           b. 点击充值按钮
           c. 获取并记录充值弹窗信息
           d. 关闭弹窗
           e. 点击下载充值按钮
           f. 获取并记录充值弹窗信息
           g. 关闭弹窗
        """
        print(f"=== 测试用例: {case_data.case_name} ===")
        # 步骤1: 登录
        login_page = LoginPage(page)
        login_page.goto_login_page()
        login_page.login_with(case_data.username, case_data.password)
        # 等待登录完成
        login_page.wait.wait_for_timeout(3000)

        print(f"✅ 登录完成，当前URL: {login_page.get_current_url()}")
        # 步骤2: 直接跳转至目标3D模型详情页
        print(f"📄 正在跳转至目标页面: {self.TARGET_URL}")
        page.goto(self.TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        print(f"✅ 已到达目标页面: {page.url}")


        # 创建model_page实例用于点击按钮
        model_page = ModelDetailPage(page)

        # 先测试单个data值验证流程
        print(f"\n{'='*70}")
        print(f"先测试单个data值验证流程")
        print(f"{'='*70}")

        test_data_values = [1,4]

        for data_value in test_data_values:
            print(f"\n{'='*70}")
            print(f"测试 data = {data_value}")
            print(f"{'='*70}")

            # 测试充值按钮
            print(f"\n--- 测试充值按钮 ---")
            # 先检查页面状态
            print(f"页面URL: {page.url}")
            print(f"点击充值按钮前，检查按钮是否可见...")

            # 点击充值按钮
            model_page.click_recharge_button()

            # 等待弹窗出现（增加等待时间）
            page.wait_for_timeout(3000)

            # 检查弹窗是否可见
            modal_visible = model_page.is_recharge_modal_visible()
            print(f"充值弹窗可见性: {modal_visible}")

            model_page.get_recharge_packages()
            #
            # # 关闭弹窗
            # model_page.close_recharge_modal()
            #
            # # 等待一下确保弹窗完全关闭
            # if not page.is_closed():
            #     page.wait_for_timeout(1000)
            #
            # # 测试下载充值按钮
            # print(f"\n--- 测试下载充值按钮 ---")
            # model_page.click_download_button()
            #
            # # 等待弹窗出现
            # page.wait_for_timeout(3000)
            #
            # # 检查弹窗是否可见
            # modal_visible = model_page.is_recharge_modal_visible()
            # print(f"下载充值弹窗可见性: {modal_visible}")
            #
            # download_result = model_page.get_recharge_packages()
            # all_results[f"data_{data_value}_download"] = download_result

            # 关闭弹窗
            model_page.close_recharge_modal()

            # 等待一下再继续下一个测试
            if not page.is_closed():
                page.wait_for_timeout(1000)

        # 保存所有结果到文件
        print(f"\n{'='*70}")
        print(f"✅ 测试完成")
        print(f"{'='*70}")


