import io
import logging
import os
import sys
from pathlib import Path

import pytest

# ─── Windows UTF-8 输出修复 ──────────────────────────────────────────────────
# Windows 默认终端编码为 GBK/cp936，会导致中文 print 输出乱码。
# 在 pytest 加载 conftest 时强制将 stdout/stderr 切换为 UTF-8，
# 同时设置 PYTHONUTF8=1 让子进程也继承 UTF-8 模式。
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "buffer") and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from common.browser_manager import BrowserManager
from common.assertions import create_assertion, enable_diagnostics, disable_diagnostics
from common.yaml_loader import load_yaml
from config.settings import DEFAULT_TIMEOUT_MS, get_config

logger = logging.getLogger(__name__)


# ─── Session 级登录态复用：所有用例共享一份 storage_state ─────────────────────
# 让全套 test 只跑一次完整登录，后续每个 test 用 storage_state 创建已登录 context。
# 仅业务用例使用；测试登录功能本身的用例继续走 page fixture（原始未登录态）。

@pytest.fixture(scope="session")
def logged_in_context(browser, request, playwright):
    """会话级已登录 context：登录与后续 test 共用同一个 context，整个 session 只开一个窗口。

    登录策略（优先级从高到低）：
    1. CookieManager 缓存有效 → 直接注入，无需网络请求（最快，~200ms）
    2. CAS API 登录（TGT → ST → 浏览器 callback）→ 跳过 UI 表单，~2-3s
    3. LoginPage UI 登录兜底 → 完整表单交互，~5-10s

    账号来源优先级（从高到低）：
    1. pytest CLI 参数 ``--login-username`` / ``--login-password``
    2. 环境变量 ``TEST_LOGIN_USERNAME`` / ``TEST_LOGIN_PASSWORD``
    3. tests/data/login_data.yaml 默认账号（向后兼容）
    """
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
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    # 导航超时兜底：防止 CDP 底层 hang 导致 goto 无限等待
    # （set_default_timeout 只覆盖元素操作，导航需单独设置）
    context.set_default_navigation_timeout(DEFAULT_TIMEOUT_MS)

    # 这个 page 不仅用于登录，还要在 session 期间保持存活——
    # Chromium headed 模式下，context 内最后一个 page 被关闭时窗口会消失，
    # 下次 new_page 会重新弹出窗口，视觉上即"浏览器关闭+重开"的闪动。
    # 留住此 page 即可让窗口贯穿整个 session 稳定存在。
    anchor_page = context.new_page()
    anchor_page.set_default_timeout(DEFAULT_TIMEOUT_MS)
    anchor_page.set_default_navigation_timeout(DEFAULT_TIMEOUT_MS)
    try:
        from common.api.auth import cas_login
        cas_login(playwright, context, anchor_page, username, password)
        logger.info("session 级登录完成（CAS API），anchor_page 将作为测试主 tab 复用至 session 结束")
    except Exception as api_err:
        logger.warning("CAS API 登录失败（%s），回退至 UI 登录", api_err)
        try:
            from pages.methods.login_page import LoginPage
            login = LoginPage(anchor_page)
            login.goto_login_page()
            login.login_with(username, password)
            logger.info("session 级登录完成（UI 兜底），anchor_page 将作为测试主 tab 复用至 session 结束")
        except Exception:
            logger.exception("session 级登录失败（CAS API + UI 均失败）")
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


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """注入浏览器稳定性启动参数，读取自 config/settings.yaml（单一来源）。

    参数在 settings.yaml → environments.<env>.browser.launch_args 中配置，
    与 BrowserManager 共享同一份配置，避免双重维护。
    """
    extra_args = [str(a) for a in get_config().current_env.browser.launch_args]
    return {
        **browser_type_launch_args,
        "args": browser_type_launch_args.get("args", []) + extra_args,
    }


@pytest.fixture(scope="function")
def logged_in_page(logged_in_context):
    """已登录态 page（方案 A：首个用例复用 anchor_page，后续用例独立 new_page）。

    设计动机：
    - 消除"登录 tab 闲置 + 另起操作 tab"的双 tab 现象——单 test 执行时全程单 tab；
    - 首个用例直接复用 session 级登录页 anchor_page（已登录、已在窗口里），不另起 tab；
    - 后续用例 new_page()、用完即关，沿用 A2 的 renderer 内存隔离，防止长批量累积崩溃；
    - anchor_page 永不在用例 teardown 关闭，作为 headed 模式窗口保活页存活至 session 结束。
    """
    anchor_page = getattr(logged_in_context, "_anchor_page", None)
    consumed = getattr(logged_in_context, "_anchor_consumed", False)

    reuse_anchor = (
        anchor_page is not None
        and not anchor_page.is_closed()
        and not consumed
    )

    if reuse_anchor:
        logged_in_context._anchor_consumed = True  # type: ignore[attr-defined]
        page = anchor_page
    else:
        page = logged_in_context.new_page()

    page.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page.set_default_navigation_timeout(DEFAULT_TIMEOUT_MS)
    try:
        yield page
    finally:
        # anchor_page 作为窗口保活页永不关闭；仅关闭后续用例新建的独立 page
        if not reuse_anchor:
            try:
                page.close()
            except Exception:
                pass


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

    # 测试结束后：关闭除主页面和 anchor_page 之外的所有标签页，防止泄漏到下一个测试
    # anchor_page 是 logged_in_context 的保活页，不得关闭（否则 headed 窗口会消失）
    try:
        context = page.context
        anchor_page = getattr(context, "_anchor_page", None)
        alive_pages = [p for p in context.pages if not p.is_closed()]
        extra = [p for p in alive_pages if p is not page and p is not anchor_page]
        if extra:
            logger.info("测试结束，开始清理 %s 个多余标签页", len(extra))
            closed = 0
            for p in extra:
                if not p.is_closed():
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


@pytest.fixture(scope="function")
def gio_tracking(request):
    """GIO 埋点捕获器：用例开始即挂 route，整用例累积事件。

    - 自动选取当前 active page（logged_in_page 优先，否则 page）；
    - 若用例同时声明了 assertion，则注入，失败落诊断 + 进 checkpoint summary；
    - teardown 时 detach route 并打印埋点校验汇总。
    """
    from common.tracking.capture import GioTrackingCapture

    page = _resolve_active_page(request)
    if page is None:
        page = request.getfixturevalue("page")

    capture = GioTrackingCapture()
    capture.test_name = request.node.name
    if "assertion" in set(getattr(request, "fixturenames", ())):
        capture.bind_assertion(request.getfixturevalue("assertion"))
    capture.attach(page)

    yield capture

    try:
        capture.detach(page)
    finally:
        try:
            terminalreporter = request.config.pluginmanager.get_plugin("terminalreporter")
            tw = getattr(terminalreporter, "_tw", None) if terminalreporter else None
            capture.print_summary(tw=tw)
        except Exception:
            capture.print_summary(tw=None)


@pytest.fixture(scope="session")
def mysql_db():
    """会话级 MySQL 薄客户端（懒连接：拿到 client 不会立即开连接）。

    用法：
        def test_xxx(self, logged_in_page, mysql_db):
            with mysql_db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT ...")
    """
    from common.db import MySQLClient
    return MySQLClient()


@pytest.fixture(scope="session")
def redis_db():
    """会话级 Redis 薄客户端（懒连接）。

    用法：
        def test_xxx(self, redis_db):
            with redis_db.client() as r:
                r.delete("znzmo:group:all")
    """
    from common.db import RedisClient
    return RedisClient()


@pytest.fixture(scope="function")
def api_client(playwright):
    """独立 API 客户端：按需带 cookie 登录态，不启动浏览器。

    有效 cookie 存在时自动带登录态（storage_state 注入）；无 cookie 则匿名。
    用法：
        def test_xxx(self, api_client, api_assert):
            resp = api_client.get("/api/something")
            api_assert.status_ok(resp, name="接口可用")
    """
    from common.api import ApiClient
    from common.api.auth import load_storage_state

    storage = load_storage_state()
    ctx = playwright.request.new_context(storage_state=storage)
    try:
        yield ApiClient(ctx)
    finally:
        try:
            ctx.dispose()
        except Exception:
            pass


@pytest.fixture(scope="function")
def logged_in_api_client(logged_in_context):
    """复用已登录浏览器 context 的 API 客户端（UI+API 混合 / 冷启动兜底）。

    保证有效登录态（浏览器已登录、cookie 新鲜）。
    适合同一用例内既操作 UI 又调接口的混合场景，或本地无 cookie 文件时兜底。
    """
    from common.api import ApiClient
    yield ApiClient(logged_in_context.request)


@pytest.fixture(scope="function")
def api_assert(request):
    """API 响应诊断断言；teardown 打印关键校验点汇总（同 assertion fixture）。

    用法：
        def test_xxx(self, api_client, api_assert):
            resp = api_client.get("/api/something")
            api_assert.status_ok(resp, name="接口可用")
            api_assert.json_path(resp, "code", 0, name="业务码为0")
    """
    from common.api import ApiAssertion

    inst = ApiAssertion(request.node.name)
    yield inst
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
        # loadgroup = 用例级分发（单文件内 test 函数被打散到多 worker）；
        # 若需顺序依赖，可在用例上加 @pytest.mark.xdist_group("name") 强制同 worker。
        if getattr(config.option, "dist", "no") in ("no", None, ""):
            config.option.dist = "loadgroup"


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
