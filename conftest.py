import logging
import os
from pathlib import Path

import pytest

from common.browser_manager import BrowserManager
from common.assertions import create_assertion, enable_diagnostics, disable_diagnostics
from common.yaml_loader import load_yaml

logger = logging.getLogger(__name__)


# ─── Session 级登录态复用：所有用例共享一份 storage_state ─────────────────────
# 让全套 test 只跑一次完整登录，后续每个 test 用 storage_state 创建已登录 context。
# 仅业务用例使用；测试登录功能本身的用例继续走 page fixture（原始未登录态）。

@pytest.fixture(scope="session")
def logged_in_context(browser, request):
    """会话级已登录 context：登录与后续 test 共用同一个 context，整个 session 只开一个窗口。

    实现要点：
    - 不再"临时 context 登录 → 关闭 → 新建持久 context"，避免 headed 模式下窗口闪动；
    - 登录在该 context 内的一个临时 tab 上完成，登录结束后只关 tab，context 保持存活；
    - 后续每个 test 在同一 context 上开新 tab（``logged_in_page``）。

    账号优先级（从高到低）：
    1. pytest CLI 参数 ``--login-username`` / ``--login-password``
    2. 环境变量 ``TEST_LOGIN_USERNAME`` / ``TEST_LOGIN_PASSWORD``
    3. tests/data/login_data.yaml 默认账号（向后兼容）
    """
    # 延迟 import，避免循环依赖
    from pages.methods.login_page import LoginPage

    # 多源账号解析
    cli_user = request.config.getoption("--login-username", default=None)
    cli_pwd  = request.config.getoption("--login-password", default=None)
    env_user = os.getenv("TEST_LOGIN_USERNAME")
    env_pwd  = os.getenv("TEST_LOGIN_PASSWORD")

    if cli_user and cli_pwd:
        username, password = cli_user, cli_pwd
        logger.info("使用 CLI 参数账号登录: %s", username)
    elif env_user and env_pwd:
        username, password = env_user, env_pwd
        logger.info("使用环境变量账号登录: %s", username)
    else:
        login_data = load_yaml("tests/data/login_data.yaml") or {}
        cases = login_data.get("cases") or []
        if not cases:
            raise RuntimeError(
                "tests/data/login_data.yaml 缺少 cases，无法初始化 session 登录态"
            )
        creds = cases[0]
        username = creds["username"]
        password = creds["password"]
        logger.info("使用 login_data.yaml 默认账号登录: %s", username)

    context = browser.new_context()
    context.set_default_timeout(30000)

    # 这个 page 不仅用于登录，还要在 session 期间保持存活——
    # Chromium headed 模式下，context 内最后一个 page 被关闭时窗口会消失，
    # 下次 new_page 会重新弹出窗口，视觉上即"浏览器关闭+重开"的闪动。
    # 留住此 page 即可让窗口贯穿整个 session 稳定存在。
    # 同时，该 page 后续被 logged_in_page fixture 直接复用为测试 page，
    # 避免每个 test 开新 tab 导致"先切 tab 再跳转"的视觉问题。
    anchor_page = context.new_page()
    anchor_page.set_default_timeout(30000)
    try:
        login = LoginPage(anchor_page)
        login.goto_login_page()
        login.login_with(username, password)
        logger.info("session 级登录完成，anchor_page 将作为测试主 tab 复用至 session 结束")
    except Exception:
        logger.exception("session 级登录失败")
        raise

    # 把 anchor_page 暴露给 logged_in_page fixture 使用
    context._anchor_page = anchor_page  # type: ignore[attr-defined]

    try:
        yield context
    finally:
        # session 结束时统一收尾：先关 anchor_page，再关 context
        try:
            if not anchor_page.is_closed():
                anchor_page.close()
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass


@pytest.fixture(scope="session")
def storage_state_path(tmp_path_factory, logged_in_context):
    """向后兼容：从已登录 context 导出 storage_state.json。

    若现有用例/工具显式依赖该 fixture，仍能拿到正确的 storage_state 文件；
    主路径已不需要 storage_state（``logged_in_context`` 自身就是登录态）。
    """
    state_file = tmp_path_factory.mktemp("auth") / "state.json"
    logged_in_context.storage_state(path=str(state_file))
    logger.info("storage_state 已导出: %s", state_file)
    return str(state_file)


@pytest.fixture(scope="function")
def logged_in_page(logged_in_context):
    """已登录态 page：直接复用会话级 anchor_page，不开新 tab。

    设计动机：
    - 此前每次 test 用 ``context.new_page()`` 开新 tab，导致 ``goto(url)`` 时
      看起来是"先切到新 tab，再发生跳转"——视觉上像多了一步切换。
    - 现改为直接 yield session 级 anchor_page，整个 session 始终在同一个 tab 内
      ``goto`` 切换 URL，与手动在浏览器中输入网址的体验一致。
    - 每个 test 结束后由 ``test_setup_teardown`` 统一清理多余 tab，
      anchor_page 自身保持存活直到 session 结束。
    """
    anchor_page = getattr(logged_in_context, "_anchor_page", None)
    if anchor_page is None or anchor_page.is_closed():
        # 兜底：anchor 异常缺失时回退到新建 tab，避免整套 session 崩溃
        page = logged_in_context.new_page()
        page.set_default_timeout(30000)
        try:
            yield page
        finally:
            try:
                page.close()
            except Exception:
                pass
        return

    yield anchor_page
    # 不在此处关闭 anchor_page —— 它要存活到 session 结束以保住浏览器窗口


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


def _resolve_active_page(request):
    """挑出当前测试真正使用的 page。

    - 若 test 显式声明了 ``logged_in_page``，优先用它；
    - 否则回退到 pytest-playwright 的 ``page``；
    - 都没有则返回 None（避免主动 getfixturevalue 触发 pytest-playwright
      额外创建一个空白窗口）。
    """
    fixture_names = set(getattr(request, "fixturenames", ()))
    if "logged_in_page" in fixture_names:
        return request.getfixturevalue("logged_in_page")
    if "page" in fixture_names:
        return request.getfixturevalue("page")
    return None


@pytest.fixture(scope="function", autouse=True)
def test_setup_teardown(request):
    """每个测试函数的前后置操作。

    不再硬依赖 pytest-playwright 的 ``page``，避免使用 ``logged_in_page``
    的用例额外开一个未使用的浏览器窗口。
    """
    enable_diagnostics()

    # 在 setup 阶段就解析 page，避免 yield 之后 fixture 已被 teardown 取不到
    page = _resolve_active_page(request)

    yield

    if page is None or page.is_closed():
        return

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
def assertion(request):
    """提供诊断性断言工具的 fixture。

    动态选取当前测试使用的 page（``logged_in_page`` 优先），避免触发
    pytest-playwright 多创建一个 page。

    yield 之后通过 pytest TerminalWriter 把关键校验点汇总打印到 stdout。
    """
    page = _resolve_active_page(request)
    if page is None:
        # 兜底：若 test 既没有 logged_in_page 也没有 page，
        # 仍走 pytest-playwright 默认 page（保持旧用例兼容）。
        page = request.getfixturevalue("page")
    test_name = request.node.name
    inst = create_assertion(page, test_name)

    yield inst

    # finalizer: 打印 checkpoint 汇总
    try:
        terminalreporter = request.config.pluginmanager.get_plugin("terminalreporter")
        tw = getattr(terminalreporter, "_tw", None) if terminalreporter else None
        inst.print_summary(tw=tw)
    except Exception:
        try:
            inst.print_summary(tw=None)
        except Exception:
            pass


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
        # 仅在用户未显式指定 --dist 时才设置默认值，避免覆盖命令行参数
        if getattr(config.option, "dist", "no") in ("no", None, ""):
            config.option.dist = "loadfile"


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
    parser.addoption(
        "--login-username",
        action="store",
        default=None,
        help="覆盖 login_data.yaml 的默认登录账号（手机号）",
    )
    parser.addoption(
        "--login-password",
        action="store",
        default=None,
        help="配合 --login-username 使用的密码",
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
