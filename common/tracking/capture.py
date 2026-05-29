"""GIO 埋点运行时拦截与校验（sync Playwright）。

attach 在用例所有触发埋点的操作之前挂 route；handler 读 POST body、解码、
累积，并始终 route.continue_() 放行（绝不阻断真实上报）。
assert_event 标识符必校、var 可选子集匹配；绑定 assertion 时失败交给
assertion 汇总，否则直接 assert 抛错。
print_summary 在用例结束时输出与 DiagnosticAssertion 相同风格的 box 表格。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from common.tracking.core import GioEvent, decode_gio_body

_logger = logging.getLogger(__name__)

# 模块级常量：仅供外部参考，类内部使用 lambda 匹配（glob 不能跨路径 `/`）
GIO_URL_PATTERN = "**growingio.com**"

# 实际匹配逻辑：捕获所有 growingio.com 域名的请求
_GIO_URL_MATCHER = staticmethod(lambda url: "growingio.com" in url)


class GioTrackingCapture:

    # ── 表格列宽（与 DiagnosticAssertion 对齐）──────────────
    _COL_W_IDX    = 4
    _COL_W_ID     = 30   # 埋点标识符
    _COL_W_EXPECT = 10   # 期望
    _COL_W_ACTUAL = 10   # 实际
    _COL_W_VAR    = 36   # var 内容

    def __init__(self) -> None:
        self._events: list[GioEvent] = []
        self._checkpoints: list[dict] = []   # {identifier, passed, count, detail, expect_vars}
        self._assertion = None
        self._page = None
        self.test_name: str = ""             # 由 fixture 注入，用于表头
        # 每个实例独立的 lambda，保证 unroute 能精确匹配同一对象
        self._url_matcher = lambda url: "growingio.com" in url

    # ── 生命周期 ─────────────────────────────────────────────
    def bind_assertion(self, assertion) -> None:
        self._assertion = assertion

    def attach(self, page) -> None:
        self._page = page
        page.route(self._url_matcher, self._handle_route)

    def detach(self, page=None) -> None:
        target = page or self._page
        if target is None:
            return
        try:
            target.unroute(self._url_matcher, self._handle_route)
        except Exception as e:
            _logger.debug("unroute 失败: %s", e)

    # ── route handler ───────────────────────────────────────
    def _handle_route(self, route) -> None:
        try:
            body = route.request.post_data_buffer
            for d in decode_gio_body(body):
                t   = d.get("t", "")
                n   = d.get("n", "")
                var = d.get("var") or {}
                if n:
                    # cstm 事件：n 字段即标识符
                    self._events.append(GioEvent.from_raw(d))
                elif t in ("ppl", "vstr") and var:
                    # 页面/会话级实验变量：var 的每个 key 视为独立可断言标识符
                    # （如 Rechargetest_2、A/B test 变量名）
                    for key in var.keys():
                        self._events.append(GioEvent(
                            identifier=key,
                            type=t,
                            vars=var,
                            raw=d,
                        ))
                # pv / page / 其他系统事件：不建立标识符，静默忽略
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
            detail = f"未捕获到埋点「{identifier}」；已捕获标识符: {captured}"
        elif not ok:
            actual = [e.vars for e in matches]
            detail = f"已触发，但 var 不满足 {vars}；实际: {actual}"
        else:
            detail = f"触发 {len(matches)} 次"
            if len(matches) > 1:
                detail += "（多次上报，请确认是否重复）"

        # 取第一条命中事件的 var（用于表格展示）
        actual_vars = matches[0].vars if matches else {}

        self._checkpoints.append({
            "identifier": identifier,
            "passed": ok,
            "count": len(matches),
            "detail": detail,
            "expect_vars": vars,
            "actual_vars": actual_vars,   # 首条命中事件的实际 var
        })

        name = f"GIO埋点[{identifier}]"
        if self._assertion is not None:
            self._assertion.assert_true(ok, name=name, message=detail)
        else:
            assert ok, detail
        return ok

    # ── 表格渲染 ─────────────────────────────────────────────
    @staticmethod
    def _col(s: str, w: int) -> str:
        """截断/填充到固定宽度。"""
        if len(s) <= w:
            return s + " " * (w - len(s))
        return s[: w - 3] + "..."

    def _render_lines(self) -> List[Tuple[str, Dict]]:
        """生成表格行列表 [(text, markup), ...]，与 DiagnosticAssertion 风格对齐。"""
        cps = self._checkpoints
        n_pass = sum(1 for c in cps if c["passed"])
        n_fail = sum(1 for c in cps if not c["passed"])

        title = f" GIO 埋点校验: {self.test_name} [{n_pass} PASS / {n_fail} FAIL] "
        # 5 列：idx + id + expect + actual + var；边框：5*" │ " = 10 + 左 "│ " = 2 → 共 +15
        total_w = (self._COL_W_IDX + self._COL_W_ID + self._COL_W_EXPECT +
                   self._COL_W_ACTUAL + self._COL_W_VAR + 15)
        title_line = "┌─" + title + "─" * max(0, total_w - len(title)) + "┐"

        header = "│ {} │ {} │ {} │ {} │ {} │".format(
            self._col("#",       self._COL_W_IDX),
            self._col("埋点标识符", self._COL_W_ID),
            self._col("期望",    self._COL_W_EXPECT),
            self._col("实际",    self._COL_W_ACTUAL),
            self._col("var 内容", self._COL_W_VAR),
        )
        sep = ("├" + "─" * (self._COL_W_IDX + 2) + "┼" +
               "─" * (self._COL_W_ID + 2) + "┼" +
               "─" * (self._COL_W_EXPECT + 2) + "┼" +
               "─" * (self._COL_W_ACTUAL + 2) + "┼" +
               "─" * (self._COL_W_VAR + 2) + "┤")

        lines: List[Tuple[str, Dict]] = [
            (title_line, {"bold": True}),
            (header,     {"bold": True}),
            (sep,        {}),
        ]

        for i, cp in enumerate(cps, start=1):
            passed = cp["passed"]
            count  = cp["count"]
            expect_vars = cp.get("expect_vars")
            actual_vars = cp.get("actual_vars", {})

            prefix = "✓" if passed else "✗"
            markup: Dict = {"green": True} if passed else {"red": True}

            # 期望列
            expect_str = "var匹配" if expect_vars else "已触发"

            # 实际列
            if count == 0:
                actual_str = "未捕获"
            elif count == 1:
                actual_str = "1 次"
            else:
                actual_str = f"{count} 次(重复)"

            # var 内容列：命中则显示首条事件的 vars，否则 "-"
            if actual_vars:
                var_str = str(actual_vars)
            else:
                var_str = "-"

            row = "│ {} │ {} │ {} │ {} │ {} │".format(
                self._col(f"{prefix}{i}", self._COL_W_IDX),
                self._col(cp["identifier"], self._COL_W_ID),
                self._col(expect_str,   self._COL_W_EXPECT),
                self._col(actual_str,   self._COL_W_ACTUAL),
                var_str,
            )
            lines.append((row, markup))

            # FAIL 时在下一行补充详细原因
            if not passed:
                err = cp["detail"][:total_w]
                err_line = "│   └─ " + err
                pad = max(0, total_w + 4 - len(err_line))
                err_line = err_line + " " * pad + "│"
                lines.append((err_line, {"red": True}))

        bottom = "└" + "─" * (total_w + 2) + "┘"
        lines.append((bottom, {}))
        return lines

    # ── 汇总输出 ─────────────────────────────────────────────
    def print_summary(self, tw=None) -> None:
        """在用例结束时输出 GIO 埋点校验表格，风格与 assertion 汇总一致。"""
        try:
            if not self._checkpoints:
                return
            print()  # 视觉分隔空行
            lines = self._render_lines()
            for text, markup in lines:
                if tw is not None:
                    try:
                        tw.line(text, **markup)
                        continue
                    except Exception:
                        pass
                print(text)
        except Exception:
            # 渲染异常绝不影响测试主流程
            pass
