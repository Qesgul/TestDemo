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
import json
from typing import Dict, List

from data_types.test_data_types import LoginCaseData
from pages.methods.login_page import LoginPage
from pages.methods.model_detail_page import ModelDetailPage
from tests.steps.test_base import load_typed_cases_from_yaml, case_ids
from core.cookie_manager import CookieManager
from core.browser_manager import BrowserManager


LOGIN_CASES = load_typed_cases_from_yaml("tests/data/login_data.yaml", LoginCaseData)
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
    def test_recharge_modal_info_with_mock(self, case_data, page, assertion):
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
        # 步骤1: 使用CookieManager进行登录
        account_identifier = case_data.username

        # 检查是否有有效的Cookie
        cookie_data = CookieManager.load_cookies(account_identifier)
        if cookie_data and CookieManager.is_cookie_valid(cookie_data, max_age_hours=24):
            print(f"✅ 检测到有效的Cookie，将使用Cookie登录")
        else:
            print(f"ℹ️ 未找到有效的Cookie，将执行正常登录流程")

        def normal_login_flow(p):
            """正常登录流程回调"""
            print("🔐 开始正常登录流程...")
            login_page = LoginPage(p)
            login_page.goto_login_page()
            login_page.login_with(case_data.username, case_data.password)
            # 等待登录完成
            login_page.wait.wait_for_timeout(3000)
            print("✅ 正常登录流程完成")
            return login_page

        # 使用CookieManager处理登录 - 会自动检查Cookie，失效则重新登录
        logged_in_page = CookieManager.login_with_cookie(
            account_identifier=account_identifier,
            login_func=normal_login_flow,
            page=page,
            max_age_hours=24
        )

        print(f"✅ 登录完成，当前URL: {logged_in_page.url}")
        # 步骤2: 直接跳转至目标3D模型详情页
        print(f"📄 正在跳转至目标页面: {self.TARGET_URL}")
        page.goto(self.TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        print(f"✅ 已到达目标页面: {page.url}")


        # 创建model_page实例用于点击按钮
        model_page = ModelDetailPage(page)

        # 存储所有测试结果
        all_results = {}

        # 先测试单个data值验证流程
        print(f"\n{'='*70}")
        print(f"先测试单个data值验证流程")
        print(f"{'='*70}")

        test_data_values = [1,4]

        for data_value in test_data_values:
            print(f"\n{'='*70}")
            print(f"测试 data = {data_value}")
            print(f"{'='*70}")

            # 设置接口mock
            self._setup_api_mock(page, data_value)

            # 等待一下确保mock设置生效
            page.wait_for_timeout(500)

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

            recharge_result = model_page.get_recharge_packages()
            all_results[f"data_{data_value}_recharge"] = recharge_result
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
        print(f"✅ 测试完成，结果已保存")
        print(f"{'='*70}")

        self._save_results(all_results)



    def _save_results(self, results: Dict):
        """
        保存测试结果到文件

        :param results: 结果字典
        """
        try:
            filename = "recharge_test_results.json"

            # 先将复杂的对象转换为可序列化的格式
            serializable_results = {}
            for key, value in results.items():
                if isinstance(value, list):
                    # 处理套餐信息列表
                    serializable_list = []
                    for item in value:
                        if hasattr(item, "__dict__"):
                            # 将对象转换为字典
                            serializable_list.append(item.__dict__)
                        else:
                            serializable_list.append(str(item))
                    serializable_results[key] = serializable_list
                elif hasattr(value, "__dict__"):
                    serializable_results[key] = value.__dict__
                else:
                    serializable_results[key] = value

            # 写入文件
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(serializable_results, f, ensure_ascii=False, indent=2, default=str)

            print(f"📄 测试结果已保存到: {filename}")
            print(f"📊 保存的结果类型: {type(serializable_results)}")
            print(f"📊 结果数量: {len(serializable_results)}")

        except Exception as e:
            print(f"❌ 保存测试结果失败: {e}")
            import traceback
            print(f"❌ 错误详情: {traceback.format_exc()}")

    def _setup_api_mock(self, page, data_value: int):
        """
        设置接口mock

        :param page: Playwright Page对象
        :param data_value: 要设置的data字段值
        """
        def handle_route(route):
            """处理接口请求"""
            print(f"🔗 拦截到接口请求: {route.request.url}")
            try:
                # 使用与真实响应完全相同的结构
                mock_response = {
                    "error": {
                        "errorCode": "0",
                        "errorMsg": "成功"
                    },
                    "data": data_value
                }

                print(f"🎭 返回Mock响应，data = {data_value}")
                print(f"   响应结构与真实接口一致")

                # 返回模拟的响应
                route.fulfill(
                    status=200,
                    headers={
                        "Content-Type": "application/json; charset=utf-8"
                    },
                    json=mock_response
                )

            except Exception as e:
                print(f"❌ Mock接口失败: {e}")
                import traceback
                print(f"堆栈: {traceback.format_exc()}")
                # 如果处理失败，继续原请求
                route.continue_()

        # 先移除旧的路由
        try:
            page.unroute(self.API_URL)
        except Exception:
            pass

        # 使用更宽松的匹配模式设置新的路由
        page.route("**/payCenter/pay/userPayIdentityV2", handle_route)
        print(f"✅ 已设置接口mock，data = {data_value}")


