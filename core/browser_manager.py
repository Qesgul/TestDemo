import os
from typing import Optional, Dict

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import (
    BASE_URL,
    BROWSER_CHANNEL,
    BROWSER_LAUNCH_ARGS,
    BROWSER_NAME,
    BROWSER_SLOW_MO_MS,
    DEFAULT_TIMEOUT_MS,
    HEADLESS,
)


class BrowserManager:
    """
    浏览器管理器 - 支持并发执行

    注意：在 pytest-xdist 并发模式下，每个 worker 进程会有自己独立的
    Playwright 实例、浏览器和页面。这种设计避免了进程间共享浏览器状态
    可能带来的问题。
    """

    # 每个进程独立的实例存储（key: 进程ID）
    _instances: Dict[int, 'BrowserManager'] = {}

    @classmethod
    def _get_current_process(cls) -> 'BrowserManager':
        """获取当前进程的 BrowserManager 实例"""
        pid = os.getpid()
        if pid not in cls._instances:
            cls._instances[pid] = cls()
        return cls._instances[pid]

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._default_context: Optional[BrowserContext] = None
        self._default_page: Optional[Page] = None

    def _ensure_playwright_started(self) -> Playwright:
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        return self._playwright

    def _launch_browser(self) -> Browser:
        playwright_instance = self._ensure_playwright_started()
        browser_type_map = {
            "chromium": playwright_instance.chromium,
            "firefox": playwright_instance.firefox,
            "webkit": playwright_instance.webkit,
        }
        if BROWSER_NAME not in browser_type_map:
            raise ValueError(f"不支持的浏览器类型: {BROWSER_NAME}，请使用 chromium/firefox/webkit")

        launch_options = {
            "headless": HEADLESS,
            "slow_mo": BROWSER_SLOW_MO_MS,
            "args": BROWSER_LAUNCH_ARGS,
        }
        if BROWSER_CHANNEL:
            launch_options["channel"] = BROWSER_CHANNEL
        return browser_type_map[BROWSER_NAME].launch(**launch_options)

    def _get_browser(self) -> Browser:
        if self._browser is None:
            self._browser = self._launch_browser()
        return self._browser

    def _get_default_page(self) -> Page:
        if self._default_page is not None and not self._default_page.is_closed():
            return self._default_page

        browser = self._get_browser()
        if self._default_context is None:
            self._default_context = browser.new_context()
        self._default_page = self._default_context.new_page()
        self._default_page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        self._default_page.goto(BASE_URL)
        return self._default_page

    def _shutdown(self) -> None:
        """关闭当前进程的浏览器资源"""
        if self._default_page is not None and not self._default_page.is_closed():
            self._default_page.close()
        if self._default_context is not None:
            self._default_context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

        self._default_page = None
        self._default_context = None
        self._browser = None
        self._playwright = None

    # ========== 类方法接口（保持向后兼容） ==========

    @classmethod
    def get_browser(cls) -> Browser:
        return cls._get_current_process()._get_browser()

    @classmethod
    def get_default_page(cls) -> Page:
        return cls._get_current_process()._get_default_page()

    @classmethod
    def shutdown(cls) -> None:
        """关闭当前进程的浏览器资源"""
        pid = os.getpid()
        if pid in cls._instances:
            cls._instances[pid]._shutdown()
            del cls._instances[pid]

    @classmethod
    def shutdown_all(cls) -> None:
        """关闭所有进程的浏览器资源（仅在主进程调用）"""
        for instance in list(cls._instances.values()):
            instance._shutdown()
        cls._instances.clear()
