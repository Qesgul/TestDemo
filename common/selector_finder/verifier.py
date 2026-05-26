"""
Locator 唯一性验证：根据 LocatorSpec 构建 Playwright locator，验证 count() == 1。
"""

from __future__ import annotations

import logging

from playwright.sync_api import Locator, Page

from common.selector_finder.models import LocatorSpec

_logger = logging.getLogger(__name__)


def build_locator(page: Page, spec: LocatorSpec) -> Locator:
    """将 LocatorSpec 转换为 Playwright Locator 对象。"""
    root = page.locator(spec.scope) if spec.scope else page

    if spec.strategy == "role":
        kwargs: dict = {"exact": spec.exact}
        if spec.name:
            kwargs["name"] = spec.name
        return root.get_by_role(spec.role, **kwargs)  # type: ignore[arg-type]

    if spec.strategy == "label":
        return root.get_by_label(spec.label or "", exact=spec.exact)

    if spec.strategy == "placeholder":
        return root.get_by_placeholder(spec.placeholder or "", exact=spec.exact)

    if spec.strategy == "text":
        return root.get_by_text(spec.text or "", exact=spec.exact)

    if spec.strategy == "test_id":
        return root.get_by_test_id(spec.test_id or "")

    if spec.strategy == "css":
        return page.locator(spec.selector or "")

    raise ValueError(f"未知定位策略: {spec.strategy!r}")


def is_unique(page: Page, spec: LocatorSpec) -> bool:
    """返回 True 当且仅当该 locator 在页面上精确命中 1 个元素。"""
    try:
        locator = build_locator(page, spec)
        count = locator.count()
        if count == 1:
            return True
        _logger.debug("locator 命中 %d 个元素（需要 1）: %s", count, spec)
        return False
    except Exception as exc:
        _logger.debug("locator 验证异常: %s | spec=%s", exc, spec)
        return False


def find_best_unique(page: Page, candidates: list[LocatorSpec]) -> LocatorSpec | None:
    """从候选列表中返回第一个命中唯一的 locator，全部失败则返回 None。"""
    for spec in candidates:
        if is_unique(page, spec):
            return spec
    return None
