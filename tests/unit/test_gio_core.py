"""Unit tests for common/tracking/core.py。

运行: pytest tests/unit/test_gio_core.py -v
"""
import json

from lzstring import LZString

from common.tracking.core import (
    decode_gio_body, parse_gio_body, parse_url_params, GioEvent,
)


def _gio_body(events) -> bytes:
    """把事件列表压成与 GrowingIO SDK 等价的 LZString 原始字节。

    GIO JS SDK 使用 LZString.compress() 压缩，字符以 UTF-16-BE 编码为字节发送。
    decode_lzstring 用 base64.b64encode(data) → decompressFromBase64 还原，
    与 utf-16-be 字节 round-trip 兼容。
    """
    json_str = json.dumps(events, ensure_ascii=False)
    compressed = LZString().compress(json_str)
    return compressed.encode("utf-16-be", errors="surrogatepass")


# ── decode_gio_body ────────────────────────────────────────────

def test_decode_single_event_list():
    body = _gio_body([{"n": "sc_coinrecharge_show", "t": "cstm", "var": {"a": "1"}}])
    out = decode_gio_body(body)
    assert out == [{"n": "sc_coinrecharge_show", "t": "cstm", "var": {"a": "1"}}]


def test_decode_multiple_events():
    body = _gio_body([{"n": "e1"}, {"n": "e2"}])
    out = decode_gio_body(body)
    assert [d["n"] for d in out] == ["e1", "e2"]


def test_decode_single_object_wrapped_into_list():
    body = _gio_body({"n": "solo"})
    out = decode_gio_body(body)
    assert out == [{"n": "solo"}]


def test_decode_empty_body_returns_empty():
    assert decode_gio_body(b"") == []
    assert decode_gio_body(None) == []


def test_decode_garbage_returns_empty_no_raise():
    assert decode_gio_body(b"\x00\x01\x02not-lz") == []


def test_parse_gio_body_is_alias():
    assert parse_gio_body is decode_gio_body


# ── GioEvent ───────────────────────────────────────────────────

def test_gioevent_from_raw_maps_fields():
    e = GioEvent.from_raw({"n": "topclick", "t": "cstm", "var": {"data3": "综合"}})
    assert e.identifier == "topclick"
    assert e.type == "cstm"
    assert e.vars == {"data3": "综合"}
    assert e.raw["n"] == "topclick"


def test_gioevent_from_raw_defaults():
    e = GioEvent.from_raw({})
    assert e.identifier == ""
    assert e.type == ""
    assert e.vars == {}


def test_gioevent_from_raw_none_var_becomes_empty_dict():
    e = GioEvent.from_raw({"n": "x", "var": None})
    assert e.vars == {}


# ── parse_url_params ───────────────────────────────────────────

def test_parse_url_params_basic():
    params = parse_url_params("https://md.znzmo.com/s.gif?bhv_type=exposure&spm=a.b.c")
    assert params["bhv_type"] == "exposure"
    assert params["spm"] == "a.b.c"


def test_parse_url_params_empty_query():
    assert parse_url_params("https://x.com/s.gif") == {}
