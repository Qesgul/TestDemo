"""GIO 埋点解码与数据类（纯逻辑，无 Playwright 依赖）。

复用 utils/gio_decoder.py 的 LZString 解压管道（GrowingIO SDK 实际编码格式）。
所有解码失败一律返回空，绝不抛异常，避免污染 Playwright route。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from utils.gio_decoder import decode_lzstring

_logger = logging.getLogger(__name__)


@dataclass
class GioEvent:
    """单条 GIO 自定义事件。"""
    identifier: str
    type: str
    vars: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_raw(cls, d: dict) -> "GioEvent":
        return cls(
            identifier=d.get("n", ""),
            type=d.get("t", ""),
            vars=d.get("var") or {},
            raw=d,
        )


def decode_gio_body(body: Optional[bytes]) -> list[dict]:
    """把 GIO 上报请求体解码为事件 dict 列表。

    流程：LZString 解压 -> json.loads -> 规范化为 list。
    任何失败（空体 / 非 LZString / 非 JSON / lzstring 未安装）均返回 []。
    """
    if not body:
        return []
    if isinstance(body, str):
        body = body.encode("utf-8", errors="ignore")
    try:
        text = decode_lzstring(body)
    except Exception as e:  # 含 RuntimeError(lzstring 缺失)
        _logger.debug("LZString 解压失败: %s", e)
        return []
    if not text:
        return []
    try:
        data: Any = json.loads(text)
    except (ValueError, TypeError) as e:
        _logger.debug("GIO body 非 JSON: %s", e)
        return []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        return [data]
    return []


# 别名：兼容 utils/埋点测试优化版本1.py 原 import 名
parse_gio_body = decode_gio_body


def parse_url_params(url: str) -> dict:
    """解析 URL query 为 dict（火山埋点 / 旧脚本复用）。

    单值键返回标量，多值键返回 list。
    """
    query = urlparse(url).query
    parsed = parse_qs(query)
    return {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}
