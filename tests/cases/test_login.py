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
    def test_login_success(self, case_data, page, assertion):
        print(f"=== 测试用例: {case_data.case_name} ===")

        login_page = LoginPage(page)
        login_page.goto_login_page()

        login_page.login_with(case_data.username, case_data.password)

        # 登录成功后，检查页面标题不再含"登录"字样（登录成功后标题会变化）
        print(f"当前页面URL: {login_page.page.url}")
        page_title = login_page.page.title()
        print(f"当前页面标题: {page_title}")
        assertion.assert_true(
            "登录" not in page_title,
            message=f"登录失败，页面标题仍含'登录'，当前标题: {page_title}"
        )
        print("✅ 登录测试完成")

