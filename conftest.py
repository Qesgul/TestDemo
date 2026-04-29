import json
import logging
from pathlib import Path

import pytest

from common.browser_manager import BrowserManager
from common.assertions import create_assertion, enable_diagnostics, disable_diagnostics
from common.gio_collector import GioCollector

logger = logging.getLogger(__name__)


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
            logger.info("测试结束，开始清理 %s 个多余标签页", len(alive_pages) - 1)
            closed = 0
            for p in alive_pages:
                if p is not page and not p.is_closed():
                    try:
                        p.close()
                        closed += 1
                    except Exception as e:
                        logger.warning("关闭标签页失败: %s", e)
                        continue
            if closed > 0:
                logger.info("成功关闭 %s 个多余标签页", closed)
    except Exception as e:
        logger.warning("标签页清理过程中出错: %s", e)


@pytest.fixture(scope="function")
def assertion(page, request):
    """
    提供诊断性断言工具的 fixture
    """
    test_name = request.node.name
    return create_assertion(page, test_name)


@pytest.fixture(scope="function")
def gio_collector(page, request):
    """
    按需启用的 GIO 采集 fixture。

    通过 `@pytest.mark.gio_capture(event_names=..., wait_ppl=...)` 配置。
    ``wait_ppl`` 为 None 时，仅当 ``event_names`` 中含非 ``sc_`` 前缀 token 时
    在 teardown 先等待 ``ppl`` 载荷；显式 ``wait_ppl=False`` 可关闭。
    """
    marker = request.node.get_closest_marker("gio_capture")
    kwargs = marker.kwargs if marker else {}
    event_names = list(kwargs.get("event_names", []) or [])
    collector = GioCollector(
        event_names=event_names,
    )
    collector.start(page)
    collector.clear()
    yield collector

    wait_ppl = kwargs.get("wait_ppl")
    if wait_ppl is None:
        wait_ppl = any(
            isinstance(n, str) and not n.startswith("sc_") for n in event_names
        )
    if wait_ppl:
        collector.wait_for_ppl_payload(timeout_ms=3_000, poll_ms=250)
    if event_names:
        collector.wait_for_event_names(
            event_names,
            timeout_ms=5_000,
            poll_ms=250,
        )

    report, report_text = collector.generate_report(event_names)
    test_name = getattr(request.node, "name", "unknown_case")
    dump_path = Path("reports") / "gio" / f"{test_name}_gio.json"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ppl_dump_path = Path("reports") / "gio" / f"{test_name}_ppl.json"
    collector.dump_ppl_to_file(str(ppl_dump_path))
    net_log = collector.get_net_log()
    track_urls = sorted(
        {
            str(item.get("url", ""))
            for item in net_log
            if isinstance(item, dict)
            and any(k in str(item.get("url", "")) for k in ("/collect", "/track"))
        }
    )
    print(report_text)
    print(f"落盘文件: {dump_path}")
    print(f"ppl 明文落盘: {ppl_dump_path} (count={len(collector.get_ppl_raw())})")
    print(f"net_log 上报 URL: {track_urls}")
    collector.stop()


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
    config.addinivalue_line(
        "markers",
        "gio_capture(event_names=None, wait_ppl=None): 开启 GIO JS Hook 采集；"
        "wait_ppl 默认仅当 event_names 含非 sc_ 前缀 token 时为 True",
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
