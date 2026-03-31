#!/usr/bin/env python
"""
简单的架构验证测试，专门用于测试我们的代码逻辑，而不需要真实网页元素
"""
import pytest
from unittest.mock import Mock, MagicMock
from data_types.test_data_types import LoginCaseData
from pages.methods.login_page import LoginPage
from tests.steps.test_base import (
    load_typed_cases_from_yaml,
    case_ids,
    TestAssertionHelper
)


def test_login_page_architecture():
    """
    测试登录页面的架构和方法是否可以正常初始化和访问
    """
    print("\n=== 测试登录页面架构 ===")

    # 创建模拟的 Playwright page 对象（不实际启动浏览器）
    mock_page = Mock()

    try:
        # 测试 LoginPage 可以使用模拟 page 实例化
        login_page = LoginPage(page=mock_page)
        print("✅ LoginPage 可以使用模拟页面初始化")
    except Exception as e:
        pytest.fail(f"❌ LoginPage 初始化失败: {e}")

    # 测试 LoginPage 有预期的方法
    expected_methods = [
        'username_input', 'password_input', 'submit_button', 'success_message_locator',
        'input_username', 'input_password', 'click_submit', 'wait_until_ready', 'login_with'
    ]
    missing_methods = [method for method in expected_methods if not hasattr(LoginPage, method)]

    assert not missing_methods, (
        f"❌ LoginPage 缺少方法: {', '.join(missing_methods)}"
    )
    print(f"✅ LoginPage 有所有预期的方法: {', '.join(expected_methods)}")


def test_data_loading_and_typing():
    """
    测试数据加载和类型转换
    """
    print("\n=== 测试数据加载和类型转换 ===")

    cases = load_typed_cases_from_yaml("tests/data/login_data.yaml", LoginCaseData)
    case_ids_list = case_ids(cases)

    assert len(cases) > 0, "❌ 没有加载到任何测试用例"
    print(f"✅ 成功加载了 {len(cases)} 个测试用例")

    # 验证第一个测试用例包含所有字段
    first_case = cases[0]
    required_fields = ["case_name", "username", "password", "expected_message"]
    missing_fields = [field for field in required_fields if not hasattr(first_case, field)]

    assert not missing_fields, (
        f"❌ 第一个测试用例缺少字段: {', '.join(missing_fields)}"
    )
    print("✅ 第一个测试用例包含所有字段")

    print(f"  - 用例名: {first_case.case_name}")
    print(f"  - 用户名: {first_case.username}")
    print(f"  - 密码: {first_case.password}")
    print(f"  - 预期消息: {first_case.expected_message}")

    # 验证数据类型
    assert isinstance(first_case.case_name, str), "❌ case_name 必须是字符串"
    assert isinstance(first_case.username, str), "❌ username 必须是字符串"
    assert isinstance(first_case.password, str), "❌ password 必须是字符串"
    assert isinstance(first_case.expected_message, str), "❌ expected_message 必须是字符串"

    print("✅ 所有字段的类型都是字符串")


def test_data_tag_filtering():
    """
    测试按标签过滤数据的功能
    """
    print("\n=== 测试标签过滤功能 ===")

    cases = load_typed_cases_from_yaml("tests/data/login_data.yaml", LoginCaseData)
    assert len(cases) > 0, "❌ 没有加载到测试用例"

    # 如果没有标签，返回所有数据
    filtered_cases = __import__('tests.steps.test_base', fromlist=['filter_cases_by_tags']).filter_cases_by_tags(cases, tags=[])
    assert len(filtered_cases) == len(cases), "❌ 标签为空时应该返回所有数据"
    print("✅ 标签为空时返回所有数据")

    print("✅ 标签过滤功能正常")


def test_assertion_helper():
    """
    测试断言辅助工具
    """
    print("\n=== 测试断言辅助工具 ===")

    # 测试静态方法
    try:
        from tests.steps.test_base import TestAssertionHelper

        # 测试断言静态方法可以访问
        methods = ['assert_true', 'assert_equal', 'assert_visible', 'assert_text', 'assert_contains']
        for method in methods:
            assert hasattr(TestAssertionHelper, method), f"❌ TestAssertionHelper 缺少方法: {method}"
            print(f"  ✓ 找到方法: {method}")
        print("✅ TestAssertionHelper 包含所有断言方法")
    except Exception as e:
        pytest.fail(f"❌ TestAssertionHelper 初始化失败: {e}")


def test_login_case_data():
    """
    测试 LoginCaseData 数据类型的创建和访问
    """
    print("\n=== 测试 LoginCaseData 数据类型 ===")

    try:
        test_case = LoginCaseData(
            case_name="test_architecture_check",
            username="test_user",
            password="test_password",
            expected_message="登录成功！"
        )

        print(f"✅ 成功创建 LoginCaseData:")
        print(f"  - 用例名: {test_case.case_name}")
        print(f"  - 用户名: {test_case.username}")
        print(f"  - 密码: {test_case.password}")
        print(f"  - 预期消息: {test_case.expected_message}")

        assert test_case.case_name == "test_architecture_check"
        assert test_case.username == "test_user"
        assert test_case.password == "test_password"
        assert test_case.expected_message == "登录成功！"
    except Exception as e:
        pytest.fail(f"❌ LoginCaseData 创建失败: {e}")


def test_page_elements_yaml_loading():
    """
    测试页面元素定位文件是否可以成功加载
    """
    print("\n=== 测试页面元素定位加载 ===")
    from common.yaml_loader import load_yaml

    try:
        elements = load_yaml("pages/elements/login_page_elements.yaml")
        assert elements is not None, "❌ 页面元素定位加载失败，结果为 None"
        assert isinstance(elements, dict), "❌ 页面元素定位不是字典类型"
        print(f"✅ 页面元素定位成功加载，包含 {len(elements)} 个元素")

        expected_elements = ["username_input", "password_input", "submit_button", "success_message"]
        missing_elements = [name for name in expected_elements if name not in elements]

        if missing_elements:
            pytest.fail(f"❌ 页面元素定位缺少元素: {', '.join(missing_elements)}")
        print(f"✅ 所有预期的页面元素定位都存在: {', '.join(expected_elements)}")

        for name, selector in elements.items():
            print(f"  - {name}: {selector}")

    except Exception as e:
        pytest.fail(f"❌ 页面元素定位加载失败: {e}")


if __name__ == "__main__":
    print("架构验证测试启动...")

    test_login_page_architecture()
    test_data_loading_and_typing()
    test_data_tag_filtering()
    test_assertion_helper()
    test_login_case_data()
    test_page_elements_yaml_loading()

    print("\n🎉 所有架构验证测试都成功通过！")
