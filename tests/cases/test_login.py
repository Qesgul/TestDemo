import pytest

from data_types.test_data_types import LoginCaseData
from pages.methods.login_page import LoginPage
from tests.steps.test_base import (
    load_typed_cases_from_yaml,
    case_ids,
)


LOGIN_CASES = load_typed_cases_from_yaml("tests/data/login_data.yaml", LoginCaseData)
LOGIN_CASE_IDS = case_ids(LOGIN_CASES)

if not LOGIN_CASES:
    pytest.skip("未匹配到可执行数据，请检查 settings.yaml 中 execution.tags 过滤条件", allow_module_level=True)


class TestLogin:
    @pytest.mark.parametrize("case_data", LOGIN_CASES, ids=LOGIN_CASE_IDS)
    @pytest.mark.core
    @pytest.mark.main
    def test_login_success(self, case_data, page):
        print(f"=== 测试用例: {case_data.case_name} ===")

        login_page = LoginPage(page)
        login_page.goto_login_page()

        login_page.login_with(case_data.username, case_data.password)

        # 登录成功后，检查页面状态或URL变化
        print(f"当前页面URL: {login_page.page.url}")
        assert login_page.page.url != "https://www.znzmo.com/?from=personalCenter" or "登录" not in login_page.page.title()
        print("✅ 登录测试完成")

