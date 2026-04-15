"""
增强版断言模块 - 支持失败时自动捕获诊断信息
包括：页面截图、DOM结构、网络日志、控制台错误
"""
import os
import json
import logging
from datetime import datetime
from typing import Any, Optional, Dict, List
from pathlib import Path

from playwright.sync_api import expect, Page, Locator

logger = logging.getLogger(__name__)


class DiagnosticAssertion:
    """诊断性断言类 - 在断言失败时自动捕获诊断信息"""

    # 诊断信息输出目录
    diagnostic_dir: str = "diagnostic_reports"
    # 是否启用诊断信息捕获
    enabled: bool = True
    # 已捕获的诊断信息计数
    capture_count: int = 0

    def __init__(self, page: Page, test_name: Optional[str] = None):
        """
        初始化诊断性断言

        :param page: Playwright Page 对象
        :param test_name: 测试名称，用于诊断信息命名
        """
        self.page = page
        self.test_name = test_name or "unknown_test"
        self._console_logs: List[Dict[str, Any]] = []
        self._network_logs: List[Dict[str, Any]] = []
        self._bind_page_listeners()
        self._setup_diagnostic_dir()

    def _bind_page_listeners(self) -> None:
        """绑定页面事件监听器，记录最近的 console/network 信息。"""
        try:
            self.page.on("console", self._on_console_message)
            self.page.on("requestfinished", self._on_request_finished)
            self.page.on("requestfailed", self._on_request_failed)
        except Exception:
            # 监听失败不影响断言主流程
            pass

    def _on_console_message(self, message) -> None:
        try:
            self._console_logs.append(
                {
                    "type": message.type,
                    "text": message.text,
                    "timestamp": datetime.now().isoformat(),
                    "location": message.location,
                }
            )
            self._console_logs = self._console_logs[-200:]
        except Exception:
            pass

    def _on_request_finished(self, request) -> None:
        try:
            response = request.response()
            self._network_logs.append(
                {
                    "event": "requestfinished",
                    "timestamp": datetime.now().isoformat(),
                    "method": request.method,
                    "url": request.url,
                    "status": response.status if response else None,
                }
            )
            self._network_logs = self._network_logs[-300:]
        except Exception:
            pass

    def _on_request_failed(self, request) -> None:
        try:
            self._network_logs.append(
                {
                    "event": "requestfailed",
                    "timestamp": datetime.now().isoformat(),
                    "method": request.method,
                    "url": request.url,
                    "failure": request.failure,
                }
            )
            self._network_logs = self._network_logs[-300:]
        except Exception:
            pass

    @classmethod
    def _setup_diagnostic_dir(cls) -> None:
        """设置诊断信息目录"""
        if not os.path.exists(cls.diagnostic_dir):
            os.makedirs(cls.diagnostic_dir, exist_ok=True)

    def _generate_diagnostic_id(self) -> str:
        """生成诊断信息ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        DiagnosticAssertion.capture_count += 1
        return f"{self.test_name}_{timestamp}_{DiagnosticAssertion.capture_count}"

    def _capture_screenshot(self, diagnostic_id: str) -> Optional[str]:
        """
        捕获页面截图

        :param diagnostic_id: 诊断信息ID
        :return: 截图文件路径
        """
        try:
            screenshot_path = os.path.join(self.diagnostic_dir, f"{diagnostic_id}_screenshot.png")
            self.page.screenshot(path=screenshot_path, full_page=True)
            return screenshot_path
        except Exception as e:
            logger.warning("截图捕获失败: %s", e)
            return None

    def _capture_dom(self, diagnostic_id: str) -> Optional[str]:
        """
        捕获页面DOM结构

        :param diagnostic_id: 诊断信息ID
        :return: DOM文件路径
        """
        try:
            dom_path = os.path.join(self.diagnostic_dir, f"{diagnostic_id}_dom.html")
            page_content = self.page.content()
            with open(dom_path, "w", encoding="utf-8") as f:
                f.write(page_content)
            return dom_path
        except Exception as e:
            logger.warning("DOM捕获失败: %s", e)
            return None

    def _capture_console_logs(self, diagnostic_id: str) -> Optional[str]:
        """
        捕获控制台日志

        :param diagnostic_id: 诊断信息ID
        :return: 日志文件路径
        """
        try:
            console_path = os.path.join(self.diagnostic_dir, f"{diagnostic_id}_console.json")
            console_errors = list(self._console_logs)
            if not console_errors:
                console_errors = [{
                    "type": "info",
                    "timestamp": datetime.now().isoformat(),
                    "text": "No captured console logs. Fallback page state.",
                    "url": self.page.url,
                    "title": self.page.title(),
                }]

            with open(console_path, "w", encoding="utf-8") as f:
                json.dump(console_errors, f, ensure_ascii=False, indent=2)
            return console_path
        except Exception as e:
            logger.warning("控制台日志捕获失败: %s", e)
            return None

    def _capture_network_logs(self, diagnostic_id: str) -> Optional[str]:
        """
        捕获网络请求日志

        :param diagnostic_id: 诊断信息ID
        :return: 网络日志文件路径
        """
        try:
            network_path = os.path.join(self.diagnostic_dir, f"{diagnostic_id}_network.json")
            network_info = {
                "timestamp": datetime.now().isoformat(),
                "url": self.page.url,
                "title": self.page.title(),
                "recent_requests": list(self._network_logs),
            }

            with open(network_path, "w", encoding="utf-8") as f:
                json.dump(network_info, f, ensure_ascii=False, indent=2)
            return network_path
        except Exception as e:
            logger.warning("网络日志捕获失败: %s", e)
            return None

    def _capture_cookies(self, diagnostic_id: str) -> Optional[str]:
        """
        捕获Cookie信息

        :param diagnostic_id: 诊断信息ID
        :return: Cookie文件路径
        """
        try:
            cookies_path = os.path.join(self.diagnostic_dir, f"{diagnostic_id}_cookies.json")
            context = self.page.context
            if context:
                cookies = context.cookies()
                with open(cookies_path, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                return cookies_path
        except Exception as e:
            logger.warning("Cookie捕获失败: %s", e)
            return None

    def _write_summary(self, diagnostic_id: str, assertion_info: Dict[str, Any],
                       files: Dict[str, Optional[str]]) -> str:
        """
        写入诊断摘要文件

        :param diagnostic_id: 诊断信息ID
        :param assertion_info: 断言信息
        :param files: 捕获的文件路径字典
        :return: 摘要文件路径
        """
        summary_path = os.path.join(self.diagnostic_dir, f"{diagnostic_id}_summary.json")
        summary = {
            "diagnostic_id": diagnostic_id,
            "test_name": self.test_name,
            "timestamp": datetime.now().isoformat(),
            "assertion": assertion_info,
            "page_info": {
                "url": self.page.url,
                "title": self.page.title()
            },
            "captured_files": files
        }

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary_path

    def capture_diagnostics(self, assertion_info: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        捕获所有诊断信息

        :param assertion_info: 断言信息字典
        :return: 捕获的文件路径字典
        """
        if not DiagnosticAssertion.enabled:
            return {}

        diagnostic_id = self._generate_diagnostic_id()
        logger.info("捕获诊断信息: %s", diagnostic_id)

        # 并行捕获各类诊断信息
        files = {
            "screenshot": self._capture_screenshot(diagnostic_id),
            "dom": self._capture_dom(diagnostic_id),
            "console": self._capture_console_logs(diagnostic_id),
            "network": self._capture_network_logs(diagnostic_id),
            "cookies": self._capture_cookies(diagnostic_id),
        }

        # 写入摘要
        files["summary"] = self._write_summary(diagnostic_id, assertion_info, files)

        logger.info("诊断信息捕获完成: %s", diagnostic_id)
        return files

    def _wrap_assertion(self, assertion_name: str, func, *args, **kwargs):
        """
        包装断言函数，在失败时捕获诊断信息

        :param assertion_name: 断言名称
        :param func: 断言函数
        :param args: 位置参数
        :param kwargs: 关键字参数
        """
        try:
            func(*args, **kwargs)
        except Exception as e:
            if DiagnosticAssertion.enabled:
                assertion_info = {
                    "name": assertion_name,
                    "args": str(args),
                    "kwargs": str(kwargs),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.capture_diagnostics(assertion_info)
            raise

    # ===== 断言方法 =====

    def assert_equal(self, actual: Any, expected: Any, message: str = ""):
        """断言相等"""
        try:
            assert actual == expected, message or f"期望 {expected}, 实际 {actual}"
        except Exception as e:
            if DiagnosticAssertion.enabled:
                assertion_info = {
                    "name": "assert_equal",
                    "args": str((actual, expected)),
                    "kwargs": "{}",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.capture_diagnostics(assertion_info)
            raise

    def assert_true(self, value: Any, message: str = ""):
        """断言为真"""
        try:
            assert value, message or f"期望为真, 实际 {value}"
        except Exception as e:
            if DiagnosticAssertion.enabled:
                assertion_info = {
                    "name": "assert_true",
                    "args": str((value,)),
                    "kwargs": "{}",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.capture_diagnostics(assertion_info)
            raise

    def assert_false(self, value: Any, message: str = ""):
        """断言为假"""
        try:
            assert not value, message or f"期望为假, 实际 {value}"
        except Exception as e:
            if DiagnosticAssertion.enabled:
                assertion_info = {
                    "name": "assert_false",
                    "args": str((value,)),
                    "kwargs": "{}",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.capture_diagnostics(assertion_info)
            raise

    def assert_in(self, member: Any, container: Any, message: str = ""):
        """断言包含"""
        try:
            assert member in container, message or f"期望 '{member}' 在 '{container}' 中"
        except Exception as e:
            if DiagnosticAssertion.enabled:
                assertion_info = {
                    "name": "assert_in",
                    "args": str((member, container)),
                    "kwargs": "{}",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.capture_diagnostics(assertion_info)
            raise

    def assert_not_in(self, member: Any, container: Any, message: str = ""):
        """断言不包含"""
        try:
            assert member not in container, message or f"期望 '{member}' 不在 '{container}' 中"
        except Exception as e:
            if DiagnosticAssertion.enabled:
                assertion_info = {
                    "name": "assert_not_in",
                    "args": str((member, container)),
                    "kwargs": "{}",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                self.capture_diagnostics(assertion_info)
            raise

    # ===== Playwright expect 包装方法 =====

    def expect_to_have_text(self, locator: Locator, expected_text: str, message: str = ""):
        """期望元素有指定文本"""
        self._wrap_assertion(
            "expect_to_have_text",
            lambda: expect(locator).to_have_text(expected_text, timeout=30000)
        )

    def expect_to_be_visible(self, locator: Locator, message: str = ""):
        """期望元素可见"""
        self._wrap_assertion(
            "expect_to_be_visible",
            lambda: expect(locator).to_be_visible(timeout=30000)
        )

    def expect_to_be_hidden(self, locator: Locator, message: str = ""):
        """期望元素隐藏"""
        self._wrap_assertion(
            "expect_to_be_hidden",
            lambda: expect(locator).to_be_hidden(timeout=30000)
        )

    def expect_url(self, url: str, message: str = ""):
        """期望URL匹配"""
        self._wrap_assertion(
            "expect_url",
            lambda: expect(self.page).to_have_url(url, timeout=30000)
        )

    def expect_title(self, title: str, message: str = ""):
        """期望标题匹配"""
        self._wrap_assertion(
            "expect_title",
            lambda: expect(self.page).to_have_title(title, timeout=30000)
        )

    def expect_to_contain_text(self, locator: Locator, text: str, message: str = ""):
        """期望元素包含文本"""
        self._wrap_assertion(
            "expect_to_contain_text",
            lambda: expect(locator).to_contain_text(text, timeout=30000)
        )


# ===== 全局便捷函数 =====

def create_assertion(page: Page, test_name: Optional[str] = None) -> DiagnosticAssertion:
    """
    创建诊断性断言实例的便捷函数

    :param page: Playwright Page 对象
    :param test_name: 测试名称
    :return: DiagnosticAssertion 实例
    """
    return DiagnosticAssertion(page, test_name)


def expect_text(locator, expected_text: str, page: Optional[Page] = None) -> None:
    """
    保持向后兼容的 expect_text 函数
    如果提供了 page，则启用诊断信息捕获
    """
    if page:
        assertion = DiagnosticAssertion(page)
        assertion.expect_to_have_text(locator, expected_text)
    else:
        expect(locator).to_have_text(expected_text)


def enable_diagnostics() -> None:
    """启用诊断信息捕获"""
    DiagnosticAssertion.enabled = True


def disable_diagnostics() -> None:
    """禁用诊断信息捕获"""
    DiagnosticAssertion.enabled = False


def set_diagnostic_dir(path: str) -> None:
    """
    设置诊断信息输出目录

    :param path: 目录路径
    """
    DiagnosticAssertion.diagnostic_dir = path
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
