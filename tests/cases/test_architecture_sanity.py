from pathlib import Path
from unittest.mock import Mock

import pytest

from common.assertions import DiagnosticAssertion
from common.browser_manager import BrowserManager
from common.cookie_manager import CookieManager
from common.yaml_loader import load_yaml
from data_types.test_data_types import LoginCaseData
from pages.base_page import BasePage
from pages.methods.login_page import LoginPage
from pages.methods.publish_work_page import PublishWorkPage
from tests.steps.test_base import case_ids, filter_cases_by_tags, load_typed_cases_from_yaml


def test_page_objects_require_explicit_page():
    with pytest.raises(ValueError):
        BasePage(page=None)

    mock_page = Mock()
    login_page = LoginPage(page=mock_page)
    publish_page = PublishWorkPage(page=mock_page)

    assert login_page.page is mock_page
    assert publish_page.page is mock_page


def test_login_page_architecture():
    mock_page = Mock()
    login_page = LoginPage(page=mock_page)

    assert login_page.page is mock_page
    for method in [
        "goto_login_page",
        "login_with",
        "login_with_password",
        "wait_until_ready",
    ]:
        assert hasattr(LoginPage, method), f"Missing method: {method}"


def test_data_loading_and_typing():
    cases = load_typed_cases_from_yaml("tests/data/login_data.yaml", LoginCaseData)
    ids = case_ids(cases)

    assert cases
    assert ids

    first_case = cases[0]
    for field in ["case_name", "username", "password", "expected_message"]:
        assert hasattr(first_case, field), f"Missing field: {field}"
        assert isinstance(getattr(first_case, field), str)


def test_core_components_import_path():
    assert BrowserManager is not None
    assert CookieManager is not None
    assert BasePage is not None
    assert DiagnosticAssertion is not None


def test_per_feature_data_yaml_convention():
    typed_paths = (
        "tests/data/login_data.yaml",
        "tests/data/recharge_flow_data.yaml",
    )
    for rel in typed_paths:
        path = Path(rel)
        assert path.is_file(), f"Missing data file: {rel}"
        cases = load_typed_cases_from_yaml(rel, LoginCaseData)
        assert cases, f"No cases parsed from: {rel}"
        first = cases[0]
        for field in ("case_name", "username", "password", "expected_message"):
            assert hasattr(first, field), f"{rel} missing field: {field}"

    inspiration_path = Path("tests/data/create_inspiration_flow_data.yaml")
    assert inspiration_path.is_file()

    raw = load_yaml("tests/data/create_inspiration_flow_data.yaml")
    assert isinstance(raw, dict) and raw
    assert raw.get("username")
    assert raw.get("password")
    assert any(key.startswith("expected_") for key in raw)


def test_data_tag_filtering():
    raw = load_yaml("tests/data/login_data.yaml")
    cases = list((raw or {}).get("cases", []))
    assert cases

    filtered_cases = filter_cases_by_tags(cases, tags=set())
    assert len(filtered_cases) == len(cases)


def test_login_case_data():
    test_case = LoginCaseData(
        case_name="test_architecture_check",
        username="test_user",
        password="test_password",
        expected_message="登录成功",
    )

    assert test_case.case_name == "test_architecture_check"
    assert test_case.username == "test_user"
    assert test_case.password == "test_password"
    assert test_case.expected_message == "登录成功"


def test_page_elements_yaml_loading():
    elements = load_yaml("pages/elements/login_page_elements.yaml")
    assert elements is not None
    assert isinstance(elements, dict)

    expected_elements = [
        "username_input",
        "password_input",
        "submit_button",
        "success_message",
    ]
    for name in expected_elements:
        assert name in elements, f"Missing element locator: {name}"


def test_publish_work_page_uses_valid_yaml():
    elements = load_yaml("pages/elements/publish_work_elements.yaml")
    assert isinstance(elements, dict)
    assert "publish_title" in elements
