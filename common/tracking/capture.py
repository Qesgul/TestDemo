"""GIO 埋点运行时拦截与校验（sync Playwright）。

attach 在用例所有触发埋点的操作之前挂 route；handler 读 POST body、解码、
累积，并始终 route.continue_() 放行（绝不阻断真实上报）。
assert_event 标识符必校、var 可选子集匹配；绑定 assertion 时失败交给
assertion 汇总，否则直接 assert 抛错。
"""
from __future__ import annotations

import logging
from typing import Optional

from common.tracking.core import GioEvent, decode_gio_body

_logger = logging.getLogger(__name__)

GIO_URL_PATTERN = "**/*growingio.com*"


class GioTrackingCapture:
    def __init__(self) -> None:
        self._events: list[GioEvent] = []
        self._checkpoints: list[dict] = []   # {identifier, passed, count, detail}
        self._assertion = None
        self._page = None

    # ── 生命周期 ─────────────────────────────────────────────
    def bind_assertion(self, assertion) -> None:
        self._assertion = assertion

    def attach(self, page) -> None:
        self._page = page
        page.route(GIO_URL_PATTERN, self._handle_route)

    def detach(self, page=None) -> None:
        target = page or self._page
        if target is None:
            return
        try:
            target.unroute(GIO_URL_PATTERN, self._handle_route)
        except Exception as e:
            _logger.debug("unroute 失败: %s", e)

    # ── route handler ───────────────────────────────────────
    def _handle_route(self, route) -> None:
        try:
            body = route.request.post_data_buffer
            for d in decode_gio_body(body):
                self._events.append(GioEvent.from_raw(d))
        except Exception as e:
            _logger.debug("GIO route 解析失败: %s", e)
        finally:
            try:
                route.continue_()
            except Exception as e:
                _logger.debug("route.continue_ 失败: %s", e)

    # ── 查询 ─────────────────────────────────────────────────
    @property
    def events(self) -> list[GioEvent]:
        return list(self._events)

    def find(self, identifier: str) -> list[GioEvent]:
        return [e for e in self._events if e.identifier == identifier]

    # ── 校验 ─────────────────────────────────────────────────
    def assert_event(self, identifier: str, vars: Optional[dict] = None) -> bool:
        matches = self.find(identifier)
        ok = bool(matches)
        if ok and vars:
            ok = any(
                all(e.vars.get(k) == v for k, v in vars.items())
                for e in matches
            )

        if not matches:
            captured = sorted({e.identifier for e in self._events if e.identifier})
            detail = f"未捕获到埋点「{identifier}」；本次已捕获标识符: {captured}"
        elif not ok:
            actual = [e.vars for e in matches]
            detail = f"埋点「{identifier}」已触发，但 var 不满足 {vars}；实际: {actual}"
        else:
            detail = f"埋点「{identifier}」触发 {len(matches)} 次"
            if len(matches) > 1:
                detail += "（多次上报，请确认是否重复）"

        self._checkpoints.append({
            "identifier": identifier,
            "passed": ok,
            "count": len(matches),
            "detail": detail,
        })

        name = f"GIO埋点[{identifier}]"
        if self._assertion is not None:
            self._assertion.assert_true(ok, name=name, message=detail)
        else:
            assert ok, detail
        return ok

    # ── 汇总 ─────────────────────────────────────────────────
    def print_summary(self, tw=None) -> None:
        if not self._checkpoints:
            return
        lines = ["", "─── GIO 埋点校验汇总 ───"]
        for c in self._checkpoints:
            icon = "✅" if c["passed"] else "❌"
            lines.append(f"  {icon} {c['identifier']}  {c['detail']}")
        text = "\n".join(lines)
        if tw is not None:
            try:
                tw.line(text)
                return
            except Exception:
                pass
        _logger.info(text)
