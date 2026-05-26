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
            return trigger.is_visible(timeout=200)
        except Exception:
            return False

    def close(self, page: Page) -> bool:
        try:
            triggers = page.locator(self.trigger_selector)
            trigger_count = triggers.count()
            for index in range(trigger_count):
                trigger = triggers.nth(index)
                if not trigger.is_visible(timeout=200):
                    continue
                if self.close_selector:
                    button = trigger.locator(self.close_selector).first
                elif self.close_text:
                    button = trigger.get_by_text(self.close_text, exact=False).first
                else:
                    return False
                if not button.is_visible(timeout=200):
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
            self._reload_to_dismiss_popups()

    def get_popup_strategies(self) -> List[PopupStrategy]:
        strategies = list(self.DEFAULT_POPUP_STRATEGIES)
        extra = self.extra_popup_strategies()
        if extra:
            strategies.extend(extra)
        return strategies

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        return []

    def close_all_popups(self, max_tries: int = 1, wait_between_tries: float = 0.3) -> int:
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

    def _has_blocking_popup(self) -> bool:
        """快速检测页面是否当前存在阻塞性弹窗（ant-modal 系列）。

        仅做一次 ``is_visible(timeout=200)``，开销极小；
        给 ``_reload_to_dismiss_popups`` 做条件判定，避免无弹窗页面无谓 reload。
        """
        try:
            return self.page.locator(
                ".ant-modal-wrap, .ant-modal-mask, .ant-modal"
            ).first.is_visible(timeout=200)
        except Exception:
            return False

    def _reload_to_dismiss_popups(self) -> None:
        """检测到阻塞弹窗时才 reload，无弹窗页面零开销零闪动。

        无条件 reload 会让用户视觉上感受到"打开 → 关闭 → 重新打开"，
        这里改为先快速探测，仅当确实存在 modal 时才刷新。
        """
        try:
            if self._has_blocking_popup():
                self.page.reload(wait_until="domcontentloaded")
        except Exception:
            pass

    def goto(
        self,
        url: str,
        close_popups_after_load: bool = True,
        wait_state: str = "domcontentloaded",
    ) -> None:
        """打开 URL 并等待加载。

        ``wait_state`` 默认 ``domcontentloaded``（早先为 ``networkidle``）。
        SPA 类页面通常无法稳定达到 networkidle，networkidle 仅在需要等
        所有 XHR/资源就绪的场景显式传入。

        ``close_popups_after_load`` 默认 ``True``：加载后调用
        ``_reload_to_dismiss_popups()`` 通过 ``page.reload()``（≈ Selenium
        ``driver.refresh()``）关闭可能的弹窗。reload 会有一次"内容重新加载"
        的视觉过渡，这是浏览器内核的固有行为，不是 bug。
        """
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.wait.wait_for_page_load(wait_state)
        except PlaywrightTimeoutError:
            if wait_state == "networkidle":
                self.wait.wait_for_page_load("domcontentloaded", timeout=10.0)
            else:
                raise
        if close_popups_after_load:
            self._reload_to_dismiss_popups()

    def get_locator(self, name: str) -> Locator:
        """从 YAML 解析元素定位器，支持两种格式：

        **格式 1 — 字符串（向后兼容）**：任意 Playwright CSS / 文本 / role 选择器字符串::

            btn: '.ant-btn:has-text("提交")'

        **格式 2 — 结构化对象（推荐）**：明确声明定位方式，框架分发到 Playwright 首选 API::

            btn:
              type: role          # getByRole
              role: button
              name: 提交
              exact: true         # 默认 false

            btn:
              type: text          # getByText
              text: 工装
              exact: true
              scope: 'div[class*="Container"]'   # 可选：先 locator(scope) 再 getByText，避免多元素命中

            btn:
              type: label         # getByLabel（表单元素）
              label: 用户名
              exact: false

            btn:
              type: placeholder   # getByPlaceholder
              placeholder: 请输入手机号

            btn:
              type: test_id       # getByTestId（data-testid）
              test_id: submit-btn

            btn:
              type: title         # getByTitle
              title: 关闭

            btn:
              type: alt_text      # getByAltText（图片）
              alt_text: 头像

            btn:
              type: css           # 显式 CSS，等同格式1
              selector: '.cls:has-text("x")'

        ``scope`` 字段（可选）：任何 type 均可附加，值为父级 CSS 选择器，
        框架先执行 ``page.locator(scope)``，再在其内部执行对应 getBy* 方法，
        用于解决 ``getByText`` / ``getByRole`` 命中多个元素的歧义问题。

        定位方式优先级（官方推荐顺序）：
        role > label > placeholder > text > alt_text > title > test_id > css
        """
        if name not in self._elements:
            raise KeyError(f"Element key not found in yaml: {name}")
        value = self._elements[name]

        # ---- 格式 1：字符串（向后兼容） ----
        if isinstance(value, str):
            return self.page.locator(value)

        # ---- 格式 2：结构化对象 ----
        if isinstance(value, dict):
            loc_type: str = str(value.get("type", "css")).lower()
            exact: bool = bool(value.get("exact", False))

            # scope：先定位父容器，再在其内执行 getBy*（解决多命中歧义）
            scope_css: Optional[str] = value.get("scope")
            root = self.page.locator(scope_css) if scope_css else self.page

            if loc_type == "role":
                kwargs: dict = {"exact": exact}
                if "name" in value:
                    kwargs["name"] = value["name"]
                if "checked" in value:
                    kwargs["checked"] = value["checked"]
                if "disabled" in value:
                    kwargs["disabled"] = value["disabled"]
                if "expanded" in value:
                    kwargs["expanded"] = value["expanded"]
                if "pressed" in value:
                    kwargs["pressed"] = value["pressed"]
                if "selected" in value:
                    kwargs["selected"] = value["selected"]
                if "level" in value:
                    kwargs["level"] = value["level"]
                return root.get_by_role(value["role"], **kwargs)

            if loc_type == "label":
                return root.get_by_label(value["label"], exact=exact)

            if loc_type == "placeholder":
                return root.get_by_placeholder(value["placeholder"], exact=exact)

            if loc_type == "text":
                return root.get_by_text(value["text"], exact=exact)

            if loc_type == "alt_text":
                return root.get_by_alt_text(value["alt_text"], exact=exact)

            if loc_type == "title":
                return root.get_by_title(value["title"], exact=exact)

            if loc_type == "test_id":
                return root.get_by_test_id(value["test_id"])

            if loc_type == "css":
                selector = value["selector"]
                return root.locator(selector) if scope_css else self.page.locator(selector)

            raise ValueError(
                f"Unknown locator type {loc_type!r} for element '{name}'. "
                f"Valid types: role, label, placeholder, text, alt_text, title, test_id, css"
            )

        raise TypeError(
            f"Unsupported locator value type for '{name}': "
            f"{type(value).__name__}. Expected str or dict."
        )

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
