"""Unit tests for checkpoint summary feature in common/assertions.py."""
from common.assertions import Checkpoint, _safe_repr


def test_checkpoint_dataclass_defaults():
    cp = Checkpoint(
        name="登录跳转",
        expected="/home",
        actual="/home",
        status="PASS",
        duration_ms=42,
    )
    assert cp.name == "登录跳转"
    assert cp.status == "PASS"
    assert cp.duration_ms == 42
    assert cp.error_msg is None
    assert cp.has_explicit_name is False


def test_safe_repr_short_value():
    assert _safe_repr("hello") == "'hello'"


def test_safe_repr_truncates_long_string():
    long = "x" * 200
    out = _safe_repr(long, max_len=80)
    assert len(out) <= 80
    assert out.endswith("...")


def test_safe_repr_handles_repr_error():
    class BadRepr:
        def __repr__(self):
            raise RuntimeError("boom")
    out = _safe_repr(BadRepr())
    assert "<BadRepr repr failed>" == out


def test_safe_repr_default_maxlen_80():
    long = "y" * 200
    out = _safe_repr(long)
    assert len(out) == 80
    assert out.endswith("...")


# ===== Task 2: _record_checkpoint =====

import time
from unittest.mock import MagicMock
from common.assertions import DiagnosticAssertion


def _make_assertion():
    """构造一个不连真实浏览器的 DiagnosticAssertion 实例。"""
    page = MagicMock()
    page.url = "http://test"
    page.title.return_value = "test"
    page.context.cookies.return_value = []
    return DiagnosticAssertion(page, test_name="unit_test")


def test_record_checkpoint_pass_basic():
    a = _make_assertion()
    start = time.perf_counter()
    a._record_checkpoint(
        name="登录跳转",
        expected="/home",
        actual="/home",
        status="PASS",
        start_perf=start,
        error_msg=None,
        fallback_name="assert_equal",
    )
    assert len(a._checkpoints) == 1
    cp = a._checkpoints[0]
    assert cp.name == "登录跳转"
    assert cp.status == "PASS"
    assert cp.has_explicit_name is True
    assert cp.error_msg is None
    assert cp.duration_ms >= 0


def test_record_checkpoint_fail_with_error():
    a = _make_assertion()
    a._record_checkpoint(
        name=None,
        expected=1,
        actual=2,
        status="FAIL",
        start_perf=time.perf_counter(),
        error_msg="期望 1, 实际 2",
        fallback_name="assert_equal",
    )
    cp = a._checkpoints[0]
    assert cp.status == "FAIL"
    assert cp.error_msg == "期望 1, 实际 2"
    assert cp.has_explicit_name is False
    assert "assert_equal" in cp.name  # fallback name used


def test_record_checkpoint_truncates_error_msg():
    a = _make_assertion()
    long_err = "x" * 500
    a._record_checkpoint(
        name="x",
        expected="",
        actual="",
        status="FAIL",
        start_perf=time.perf_counter(),
        error_msg=long_err,
        fallback_name="assert_true",
    )
    assert len(a._checkpoints[0].error_msg) <= 80


def test_record_checkpoint_swallows_internal_errors():
    """Even if _record itself errors, must not raise."""
    a = _make_assertion()

    class Bad:
        def __repr__(self):
            raise RuntimeError("boom")

    # 应不抛
    a._record_checkpoint(
        name="x",
        expected=Bad(),
        actual=Bad(),
        status="PASS",
        start_perf=time.perf_counter(),
        error_msg=None,
        fallback_name="x",
    )
    # 仍应记录一条
    assert len(a._checkpoints) == 1


# ===== Task 3: assert_* methods =====

import pytest


def test_assert_equal_records_pass_with_explicit_name():
    a = _make_assertion()
    a.assert_equal(1, 1, name="数量校验")
    assert len(a._checkpoints) == 1
    cp = a._checkpoints[0]
    assert cp.name == "数量校验"
    assert cp.status == "PASS"
    assert cp.has_explicit_name is True


def test_assert_equal_records_fail_and_reraises():
    a = _make_assertion()
    from common.assertions import disable_diagnostics, enable_diagnostics
    disable_diagnostics()
    try:
        with pytest.raises(AssertionError):
            a.assert_equal(1, 2, name="数量校验")
    finally:
        enable_diagnostics()
    assert len(a._checkpoints) == 1
    assert a._checkpoints[0].status == "FAIL"
    assert a._checkpoints[0].error_msg is not None


def test_assert_equal_fallback_name_when_no_name_passed():
    a = _make_assertion()
    a.assert_equal(1, 1)
    cp = a._checkpoints[0]
    assert cp.has_explicit_name is False
    assert "assert_equal" in cp.name


def test_assert_true_records():
    a = _make_assertion()
    a.assert_true(True, name="登录成功")
    assert a._checkpoints[0].status == "PASS"
    assert a._checkpoints[0].name == "登录成功"


def test_assert_false_records():
    a = _make_assertion()
    a.assert_false(False, name="未报错")
    assert a._checkpoints[0].status == "PASS"


def test_assert_in_records_with_expected_format():
    a = _make_assertion()
    a.assert_in("a", "abc", name="包含 a")
    cp = a._checkpoints[0]
    assert cp.status == "PASS"
    assert "包含" in cp.expected


def test_assert_not_in_records():
    a = _make_assertion()
    a.assert_not_in("z", "abc", name="不含 z")
    assert a._checkpoints[0].status == "PASS"
