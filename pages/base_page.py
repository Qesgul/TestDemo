"""
Base page object with shared locator, popup, wait, and tab helpers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from common.wait_utils import WaitUtils
from common.yaml_loader import load_yaml

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PopupStrategy:
    name: str
    trigger_selector: str
    close_selector: Optional[str] = None
    close_text: Optional[str] = None
    post_close_wait_ms: int = 300

    def matches(self, page: Page) -> bool:
        try:
            trigger = page.locator(self.trigger_selector).first
            return trigger.is_visible(timeout=500)
        except Exception:
            return False

    def close(self, page: Page) -> bool:
        try:
            triggers = page.locator(self.trigger_selector)
            trigger_count = triggers.count()
            for index in range(trigger_count):
                trigger = triggers.nth(index)
                if not trigger.is_visible(timeout=500):
                    continue
                if self.close_selector:
                    button = trigger.locator(self.close_selector).first
                elif self.close_text:
                    button = trigger.get_by_text(self.close_text, exact=False).first
                else:
                    return False
                if not button.is_visible(timeout=500):
                    continue
                button.click(force=True)
                page.wait_for_timeout(self.post_close_wait_ms)
                return True
        except Exception:
            pass
        return False


class BasePage:
    DEFAULT_POPUP_STRATEGIES: tuple[PopupStrategy, ...] = (
        PopupStrategy(
            name="ant_modal_close",
            trigger_selector=".ant-modal, [role='dialog']",
            close_selector=".ant-modal-close, button.ant-modal-close",
        ),
        PopupStrategy(
            name="generic_close_button",
            trigger_selector=".modal, .popup, .dialog, [role='dialog']",
            close_selector="button[class*='close'], .close-btn, [class*='closeIcon']",
        ),
        PopupStrategy(
            name="generic_close_text",
            trigger_selector=".modal, .popup, .dialog, [role='dialog']",
            close_text="关闭",
        ),
        PopupStrategy(
            name="generic_x_text",
            trigger_selector=".modal, .popup, .dialog, [role='dialog']",
            close_text="×",
        ),
    )

    def __init__(
        self,
        page: Page,
        elements_yaml_path: Optional[str] = None,
        auto_close_popups: bool = False,
    ) -> None:
        if page is None:
            raise ValueError(
                "Page objects require an explicit Playwright page. "
                "Use the pytest page fixture or BrowserManager.create_page()."
            )
        self.page = page
        self._elements: dict[str, Any] = {}
        if elements_yaml_path:
            self._elements = load_yaml(elements_yaml_path) or {}

        self.wait = WaitUtils(self.page)

        if auto_close_popups:
            self.close_all_popups()

    def get_popup_strategies(self) -> List[PopupStrategy]:
        strategies = list(self.DEFAULT_POPUP_STRATEGIES)
        extra = self.extra_popup_strategies()
        if extra:
            strategies.extend(extra)
        return strategies

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        return []

    def close_all_popups(self, max_tries: int = 3, wait_between_tries: float = 0.5) -> int:
        closed = 0
        strategies = self.get_popup_strategies()
        for _ in range(max_tries):
            closed_this_round = 0
            for strategy in strategies:
                if not strategy.matches(self.page):
                    continue
                if strategy.close(self.page):
                    closed += 1
                    closed_this_round += 1
                else:
                    _logger.debug("Popup strategy failed to close: %s", strategy.name)
            if closed_this_round == 0:
                break
            self.page.wait_for_timeout(int(wait_between_tries * 1000))
        return closed

    def goto(
        self,
        url: str,
        close_popups_after_load: bool = True,
        wait_state: str = "networkidle",
    ) -> None:
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.wait.wait_for_page_load(wait_state)
        except PlaywrightTimeoutError:
            if wait_state == "networkidle":
                self.wait.wait_for_page_load("domcontentloaded", timeout=10.0)
            else:
                raise
        if close_popups_after_load:
            self.close_all_popups()

    def get_locator(self, name: str) -> Locator:
        if name not in self._elements:
            raise KeyError(f"Element key not found in yaml: {name}")
        return self.page.locator(str(self._elements[name]))

    def wait_for_element(self, selector: str, state: str = "visible") -> Locator:
        element = self.page.locator(selector)
        element.wait_for(state=state)
        return element

    def fill(self, selector: str, value: str) -> None:
        self.wait_for_element(selector).fill(value)

    def click(self, selector: str) -> None:
        self.wait_for_element(selector).click()

    def click_if_visible(self, selector: str) -> bool:
        locator = self.page.locator(selector)
        if not locator.is_visible():
            return False
        locator.click()
        return True

    def text_of(self, selector: str) -> str:
        return self.wait_for_element(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        return self.page.locator(selector).is_visible()

    def switch_to_page(self, target_page: Page) -> None:
        self.page = target_page
        self.wait = WaitUtils(self.page)

    def switch_to_new_tab(
        self,
        locator: Locator,
        timeout: int = 30000,
        wait_state: str = "domcontentloaded",
        click_kwargs: Optional[dict] = None,
    ) -> Page:
        click_kwargs = click_kwargs or {}
        context = self.page.context
        with context.expect_page(timeout=timeout) as new_page_info:
            locator.click(**click_kwargs)
        new_page: Page = new_page_info.value
        new_page.wait_for_load_state(wait_state, timeout=timeout)
        self.switch_to_page(new_page)
        return new_page

    def close_current_and_switch_back(self) -> Page:
        context = self.page.context
        if not self.page.is_closed():
            self.page.close()

        alive_pages: List[Page] = [p for p in context.pages if not p.is_closed()]
        if not alive_pages:
            raise RuntimeError("All tabs are closed; cannot switch back.")
        self.switch_to_page(alive_pages[-1])
        return self.page

    def close_current_and_switch_to_original(self, original_page: Page) -> Page:
        if self.page is not original_page and not self.page.is_closed():
            self.page.close()

        if original_page.is_closed():
            raise RuntimeError("Original page is already closed; cannot switch back.")

        self.switch_to_page(original_page)
        return self.page

    def close_other_tabs(self) -> int:
        context = self.page.context
        closed = 0
        for p in context.pages:
            if p is not self.page and not p.is_closed():
                try:
                    p.close()
                    closed += 1
                except Exception:
                    pass
        return closed

    def get_all_alive_pages(self) -> List[Page]:
        context = self.page.context
        return [p for p in context.pages if not p.is_closed()]

    def get_current_url(self) -> str:
        return str(self.page.evaluate("window.location.href"))
