"""Unit tests for common/tracking/capture.py。

运行: pytest tests/unit/test_gio_capture.py -v
"""
import json

import pytest
from lzstring import LZString

from common.tracking.capture import GioTrackingCapture


def _gio_body(events) -> bytes:
    json_str = json.dumps(events, ensure_ascii=False)
    compressed = LZString().compress(json_str)
    return compressed.encode("utf-16-be", errors="surrogatepass")


class _FakeRequest:
    def __init__(self, body: bytes):
        self.post_data_buffer = body


class _FakeRoute:
    """记录 continue_ 是否被调用。"""
    def __init__(self, body: bytes):
        self.request = _FakeRequest(body)
        self.continued = False

    def continue_(self):
        self.continued = True


class _FakeAssertion:
    """模拟 conftest assertion fixture 的 assert_true。"""
    def __init__(self):
        self.calls = []

    def assert_true(self, cond, name=None, message=None):
        self.calls.append((bool(cond), name, message))


def _feed(capture: GioTrackingCapture, events):
    route = _FakeRoute(_gio_body(events))
    capture._handle_route(route)
    return route


# ── 拦截累积 ───────────────────────────────────────────────────

def test_handle_route_accumulates_events():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "sc_coinrecharge_show", "var": {}}])
    assert [e.identifier for e in cap.events] == ["sc_coinrecharge_show"]


def test_handle_route_always_continues():
    cap = GioTrackingCapture()
    route = _feed(cap, [{"n": "x"}])
    assert route.continued is True


def test_handle_route_garbage_still_continues_no_raise():
    cap = GioTrackingCapture()
    route = _FakeRoute(b"garbage")
    cap._handle_route(route)
    assert route.continued is True
    assert cap.events == []


def test_find_filters_by_identifier():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "a"}, {"n": "b"}, {"n": "a"}])
    assert len(cap.find("a")) == 2
    assert len(cap.find("b")) == 1
    assert cap.find("missing") == []


# ── assert_event：标识符必校 ────────────────────────────────────

def test_assert_event_pass_on_identifier():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "sc_coinrecharge_show"}])
    assert cap.assert_event("sc_coinrecharge_show") is True


def test_assert_event_fail_when_missing_raises():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "other"}])
    with pytest.raises(AssertionError) as ei:
        cap.assert_event("sc_coinrecharge_show")
    # 失败信息要附带已捕获标识符，便于排查
    assert "other" in str(ei.value)


# ── assert_event：var 子集匹配 ──────────────────────────────────

def test_assert_event_var_subset_pass():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "topclick", "var": {"data3": "综合", "data4": "3D模型"}}])
    assert cap.assert_event("topclick", vars={"data3": "综合"}) is True


def test_assert_event_var_mismatch_raises():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "topclick", "var": {"data3": "综合"}}])
    with pytest.raises(AssertionError):
        cap.assert_event("topclick", vars={"data3": "错误值"})


# ── 与 assertion fixture 协作 ───────────────────────────────────

def test_bind_assertion_routes_to_assert_true_pass():
    cap = GioTrackingCapture()
    fake = _FakeAssertion()
    cap.bind_assertion(fake)
    _feed(cap, [{"n": "sc_coinrecharge_show"}])
    cap.assert_event("sc_coinrecharge_show")
    assert fake.calls and fake.calls[0][0] is True


def test_bind_assertion_routes_to_assert_true_fail_no_raise():
    """绑定 assertion 时，失败交给 assertion（不直接 raise，由 fixture 汇总）。"""
    cap = GioTrackingCapture()
    fake = _FakeAssertion()
    cap.bind_assertion(fake)
    cap.assert_event("missing")
    assert fake.calls and fake.calls[0][0] is False


def test_print_summary_no_crash_without_tw():
    cap = GioTrackingCapture()
    _feed(cap, [{"n": "x"}])
    cap.assert_event("x")
    cap.print_summary(tw=None)  # 不应抛异常
