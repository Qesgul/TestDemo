import logging
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, Optional

import pytest
from playwright.sync_api import Locator, Page, expect

from config.settings import ACTIVE_TAGS
from common.yaml_loader import load_yaml

T = TypeVar("T")


# ================== 测试数据加载相关（静态方法/函数）==================
def active_tags() -> set[str]:
    return {tag.strip() for tag in ACTIVE_TAGS if tag.strip()}


def load_cases_from_yaml(relative_path: str, key: str = "cases") -> list[dict[str, Any]]:
    payload = load_yaml(relative_path) or {}
    return list(payload.get(key, []))


def filter_cases_by_tags(cases: list[dict[str, Any]], tags: Optional[set[str]] = None) -> list[dict[str, Any]]:
    runtime_tags = tags if tags is not None else active_tags()
    if not runtime_tags:
        return cases
    filtered: list[dict[str, Any]] = []
    for item in cases:
        case_tags = {str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()}
        if case_tags & runtime_tags:
            filtered.append(item)
    return filtered


def to_objects(cases: list[dict[str, Any]], data_type: type[T]) -> list[T]:
    return [data_type(**item) for item in cases]


def load_typed_cases_from_yaml(relative_path: str, data_type: type[T], key: str = "cases") -> list[T]:
    raw_cases = load_cases_from_yaml(relative_path, key=key)
    filtered_cases = filter_cases_by_tags(raw_cases)
    return to_objects(filtered_cases, data_type)


def case_ids(cases: list[Any], id_field: str = "case_name") -> list[str]:
    return [str(getattr(item, id_field)) for item in cases]


def get_case_by_name(cases: list[Any], case_name: str, id_field: str = "case_name") -> Any:
    for item in cases:
        if str(getattr(item, id_field)) == case_name:
            return item
    raise ValueError(f"未找到用例数据: {case_name}")


# ================== 断言相关类（不含 __init__ 构造函数）==================
class TestAssertionHelper:
    """测试断言辅助类（不含 __init__，可被测试类继承）"""
    __test__ = False
    _page: Optional[Page] = None
    _case_name: str = "unknown_case"
    _soft_failures: list[str] = []
    _logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _capture_failure_artifacts(page: Page, case_name: str, message: str) -> None:
        screenshot_dir = Path("reports") / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        screenshot_name = f"{case_name}_{timestamp}.png"
        screenshot_path = screenshot_dir / screenshot_name
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger = logging.getLogger(TestAssertionHelper.__name__)
        logger.error("断言失败: %s", message)
        logger.error("失败截图: %s", screenshot_path)
        print(f"[ASSERT-FAIL] {message}")
        print(f"[ASSERT-FAIL] screenshot={screenshot_path}")

    @staticmethod
    def _handle_assertion_failure(page: Page, case_name: str, message: str, soft: bool, soft_failures: list[str]) -> None:
        TestAssertionHelper._capture_failure_artifacts(page, case_name, message)
        if soft:
            soft_failures.append(message)
            return
        pytest.fail(message)

    @staticmethod
    def assert_true(condition: bool, page: Page, case_name: str,
                   message: str = "条件不为True", soft: bool = False,
                   soft_failures: list[str] = None) -> None:
        if soft_failures is None:
            soft_failures = []
        if condition:
            return
        TestAssertionHelper._handle_assertion_failure(page, case_name, message, soft, soft_failures)

    @staticmethod
    def assert_equal(actual: Any, expected: Any, page: Page, case_name: str,
                     message: str = "", soft: bool = False,
                     soft_failures: list[str] = None) -> None:
        if soft_failures is None:
            soft_failures = []
        if actual == expected:
            return
        fail_message = message or f"值不相等: actual={actual}, expected={expected}"
        TestAssertionHelper._handle_assertion_failure(page, case_name, fail_message, soft, soft_failures)

    @staticmethod
    def assert_visible(locator: Locator, page: Page, case_name: str,
                      message: str = "元素不可见", soft: bool = False,
                      soft_failures: list[str] = None) -> None:
        if soft_failures is None:
            soft_failures = []
        try:
            expect(locator).to_be_visible()
        except AssertionError:
            TestAssertionHelper._handle_assertion_failure(page, case_name, message, soft, soft_failures)

    @staticmethod
    def assert_text(locator: Locator, expected_text: str, page: Page, case_name: str,
                   message: str = "", soft: bool = False,
                   soft_failures: list[str] = None) -> None:
        if soft_failures is None:
            soft_failures = []
        try:
            expect(locator).to_have_text(expected_text)
        except AssertionError:
            fail_message = message or f"文本断言失败: expected='{expected_text}'"
            TestAssertionHelper._handle_assertion_failure(page, case_name, fail_message, soft, soft_failures)

    @staticmethod
    def assert_contains(actual_text: str, expected_part: str, page: Page, case_name: str,
                      message: str = "", soft: bool = False,
                      soft_failures: list[str] = None) -> None:
        if soft_failures is None:
            soft_failures = []
        if expected_part in actual_text:
            return
        fail_message = message or f"文本不包含预期内容: expected_part='{expected_part}', actual='{actual_text}'"
        TestAssertionHelper._handle_assertion_failure(page, case_name, fail_message, soft, soft_failures)

    @staticmethod
    def assert_all_soft(soft_failures: list[str]) -> None:
        if not soft_failures:
            return
        summary = "软断言失败汇总:\n- " + "\n- ".join(soft_failures)
        pytest.fail(summary)


# ================== pytest Fixture 方式 ==================
@pytest.fixture
def assertion_helper(page: Page, request):
    case_name = getattr(request.node, "case_name", "unknown_case")
    logger = logging.getLogger("TestAssertionHelper")
    soft_failures: list[str] = []

    yield {
        "page": page,
        "case_name": case_name,
        "soft_failures": soft_failures,
        "logger": logger,
        "assert_true": lambda cond, msg="", soft=False:
            TestAssertionHelper.assert_true(cond, page, case_name, msg, soft, soft_failures),
        "assert_equal": lambda act, exp, msg="", soft=False:
            TestAssertionHelper.assert_equal(act, exp, page, case_name, msg, soft, soft_failures),
        "assert_visible": lambda loc, msg="", soft=False:
            TestAssertionHelper.assert_visible(loc, page, case_name, msg, soft, soft_failures),
        "assert_text": lambda loc, exp, msg="", soft=False:
            TestAssertionHelper.assert_text(loc, exp, page, case_name, msg, soft, soft_failures),
        "assert_contains": lambda act, exp_part, msg="", soft=False:
            TestAssertionHelper.assert_contains(act, exp_part, page, case_name, msg, soft, soft_failures),
        "assert_all_soft": lambda:
            TestAssertionHelper.assert_all_soft(soft_failures),
    }

    # Auto assert soft failures after test completes
    call_report = getattr(request.node, "rep_call", None)
    if call_report is not None and call_report.failed:
        return
    if soft_failures:
        TestAssertionHelper.assert_all_soft(soft_failures)
