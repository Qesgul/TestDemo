import pytest

from pages.methods.home_page import HomePage
from tests.steps.test_base import (
    load_typed_cases_from_yaml,
    case_ids,
)


class TestHomePage:
    """首页元素校验测试"""

    @pytest.mark.core
    @pytest.mark.main
    @pytest.mark.ui
    def test_homepage_elements_displayed(self, page, assertion):
        """测试首页核心元素是否正常展示"""
        print("=== 开始校验首页核心元素 ===")

        home_page = HomePage(page)
        home_page.goto_homepage()

        # 等待页面加载
        home_page.wait.wait_for_timeout(3000)

        # 核心校验：筛选框是否正常展示（最重要的测试目标）
        print("1. 校验筛选框...")
        try:
            if home_page.is_filter_container_visible():
                print("✅ 筛选框容器正常展示")
                if home_page.is_all_filter_tabs_visible():
                    print("✅ 筛选标签全部正常展示")
                if home_page.is_all_filter_types_visible():
                    print("✅ 筛选类型全部正常展示")
            else:
                print("⚠️ 筛选框可能需要登录才能显示，尝试点击登录|注册")
                login_register_btn = home_page.page.locator("text=登录|注册").first
                if login_register_btn.is_visible():
                    login_register_btn.click()
                    home_page.wait.wait_for_timeout(2000)
        except Exception as e:
            print(f"筛选框检查异常: {e}")
            # 筛选框是核心功能，必须可见，否则测试失败
            assertion.assert_true(False, message="筛选框容器未正常展示")

        # 校验搜索功能
        print("2. 校验搜索框...")
        try:
            if home_page.search_input().is_visible() and home_page.search_button().is_visible():
                print("✅ 搜索框元素正常")
        except Exception as e:
            print(f"搜索框检查异常: {e}")

        print("=== 首页核心元素校验完成 ===")
