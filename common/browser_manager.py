import os
from typing import Dict, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import get_config


class BrowserManager:
    """
    Explicit browser factory for parallel or non-pytest scenarios.

    In pytest-xdist runs, each worker process owns an isolated BrowserManager
    instance and its Playwright/browser resources.
    """

    _instances: Dict[int, "BrowserManager"] = {}

    @classmethod
    def _get_current_process(cls) -> "BrowserManager":
        pid = os.getpid()
        if pid not in cls._instances:
            cls._instances[pid] = cls()
        return cls._instances[pid]

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._default_context: Optional[BrowserContext] = None
        self._default_page: Optional[Page] = None

    @staticmethod
    def _config():
        return get_config()

    def _ensure_playwright_started(self) -> Playwright:
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        return self._playwright

    def _launch_browser(self) -> Browser:
        playwright_instance = self._ensure_playwright_started()
        config = self._config()
        browser_config = config.current_env.browser
        browser_name = str(browser_config.name).lower()
        browser_type_map = {
            "chromium": playwright_instance.chromium,
            "firefox": playwright_instance.firefox,
            "webkit": playwright_instance.webkit,
        }
        if browser_name not in browser_type_map:
            raise ValueError(
                f"Unsupported browser type: {browser_name}. "
                "Use chromium/firefox/webkit."
            )

        launch_options = {
            "headless": config.current_env.headless,
            "slow_mo": int(browser_config.slow_mo_ms),
            "args": [str(arg) for arg in browser_config.launch_args],
        }
        channel = str(browser_config.channel).strip()
        if channel:
            launch_options["channel"] = channel
        return browser_type_map[browser_name].launch(**launch_options)

    def _get_browser(self) -> Browser:
        if self._browser is None:
            self._browser = self._launch_browser()
        return self._browser

    def _create_context(self) -> BrowserContext:
        return self._get_browser().new_context()

    def _create_page(
        self,
        *,
        context: Optional[BrowserContext] = None,
        goto_base_url: bool = True,
    ) -> Page:
        config = self._config()
        effective_context = context or self._create_context()
        page = effective_context.new_page()
        page.set_default_timeout(config.current_env.default_timeout_ms)
        if goto_base_url:
            page.goto(config.current_env.base_url)
        return page

    def _get_default_page(self) -> Page:
        if self._default_page is not None and not self._default_page.is_closed():
            return self._default_page

        if self._default_context is None:
            self._default_context = self._create_context()
        self._default_page = self._create_page(context=self._default_context)
        return self._default_page

    def _shutdown(self) -> None:
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

    @classmethod
    def get_browser(cls) -> Browser:
        return cls._get_current_process()._get_browser()

    @classmethod
    def create_context(cls) -> BrowserContext:
        return cls._get_current_process()._create_context()

    @classmethod
    def create_page(
        cls,
        *,
        context: Optional[BrowserContext] = None,
        goto_base_url: bool = True,
    ) -> Page:
        return cls._get_current_process()._create_page(
            context=context,
            goto_base_url=goto_base_url,
        )

    @classmethod
    def get_default_page(cls) -> Page:
        """
        Compatibility helper for explicit non-page-object scenarios only.
        """
        return cls._get_current_process()._get_default_page()

    @classmethod
    def shutdown(cls) -> None:
        pid = os.getpid()
        if pid in cls._instances:
            cls._instances[pid]._shutdown()
            del cls._instances[pid]

    @classmethod
    def shutdown_all(cls) -> None:
        for instance in list(cls._instances.values()):
            instance._shutdown()
        cls._instances.clear()
