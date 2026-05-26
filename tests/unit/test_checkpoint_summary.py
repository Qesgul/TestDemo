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
