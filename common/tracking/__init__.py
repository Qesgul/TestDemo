"""GIO 埋点捕获校验子包（精简版）。

仅包含：解码（core）、运行时拦截校验（capture）、期望加载（expectations）。
不含表格解析 / 名称补全 / 代码生成。
"""
from common.tracking.core import (
    GioEvent, decode_gio_body, parse_gio_body, parse_url_params,
)
from common.tracking.capture import GioTrackingCapture, GIO_URL_PATTERN
from common.tracking.expectations import (
    GioExpectation, load_gio_expectations, parse_tracking_section,
)

__all__ = [
    "GioEvent", "decode_gio_body", "parse_gio_body", "parse_url_params",
    "GioTrackingCapture", "GIO_URL_PATTERN",
    "GioExpectation", "load_gio_expectations", "parse_tracking_section",
]
