import pytest
import sys
import traceback
import os

from core.browser_manager import BrowserManager
from common.retry_utils import should_retry, RETRY_EXCEPTIONS
from common.assertions import create_assertion, enable_diagnostics, disable_diagnostics
from config.settings import get_config


@pytest.fixture(scope="session", autouse=True)
def browser_lifecycle():
    """
    浏览器生命周期管理

    在 pytest-xdist 并发模式下，每个 worker 进程有自己独立的
    浏览器实例。这个 fixture 在每个 worker 进程的会话结束时
    关闭该进程的浏览器资源。
    """
    # 初始化在首次页面对象创建时自动完成；这里仅统一做会话级资源回收
    yield
    BrowserManager.shutdown()


@pytest.fixture(scope="function", autouse=True)
def test_setup_teardown(page):
    """
    每个测试函数的前后置操作
    :param page: Playwright page fixture
    """
    enable_diagnostics()

    yield

    # 测试结束后：关闭除主页面之外的所有标签页，防止泄漏到下一个测试
    try:
        context = page.context
        alive_pages = [p for p in context.pages if not p.is_closed()]
        if len(alive_pages) > 1:
            print(f"\n🔄 测试结束，清理 {len(alive_pages) - 1} 个多余标签页...")
            closed = 0
            for p in alive_pages:
                if p is not page and not p.is_closed():
                    try:
                        p.close()
                        closed += 1
                    except Exception as e:
                        print(f"⚠️ 关闭标签页失败: {e}")
                        continue
            if closed > 0:
                print(f"✅ 成功关闭 {closed} 个多余标签页")
    except Exception as e:
        print(f"⚠️ 标签页清理过程中出错: {e}")


@pytest.fixture(scope="function")
def assertion(page, request):
    """
    提供诊断性断言工具的 fixture
    """
    test_name = request.node.name
    return create_assertion(page, test_name)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


def pytest_configure(config):
    """
    pytest 配置
    """
    # 注册标记
    config.addinivalue_line(
        "markers", "flaky: 标记为不稳定的测试用例，会进行异常类型定向重试"
    )
    config.addinivalue_line(
        "markers", "no_diagnostics: 禁用诊断信息捕获"
    )

    # 检查 pytest-xdist 兼容性
    if config.pluginmanager.hasplugin("xdist"):
        # 设置 xdist 插件配置，避免共享资源竞争问题
        # 使用 loadfile 分发模式，按文件分配测试到不同 worker
        config.option.dist = "loadfile"
        # 禁用 xdist 的自动分发调试信息
        config.option.traceconfig = False


def pytest_addoption(parser):
    """
    添加命令行选项
    """
    parser.addoption(
        "--no-diagnostics",
        action="store_true",
        default=False,
        help="禁用断言失败时的诊断信息捕获"
    )
    parser.addoption(
        "--diagnostic-dir",
        action="store",
        default="diagnostic_reports",
        help="诊断信息输出目录"
    )
    parser.addoption(
        "--max-reruns",
        action="store",
        type=int,
        default=2,
        help="最大重试次数（默认: 2）"
    )


def pytest_sessionstart(session):
    """
    会话开始
    """
    if session.config.getoption("--no-diagnostics"):
        disable_diagnostics()
    else:
        enable_diagnostics()

    from common.assertions import set_diagnostic_dir
    set_diagnostic_dir(session.config.getoption("--diagnostic-dir"))


def pytest_collection_modifyitems(config, items):
    """
    修改测试项
    """
    for item in items:
        # 为标记了 flaky 的用例添加重试配置
        if "flaky" in item.keywords:
            item.user_properties.append(("retry_enabled", True))
            item.user_properties.append(("max_reruns", config.getoption("--max-reruns")))
