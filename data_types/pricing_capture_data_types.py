# -*- coding: utf-8 -*-
"""定价采集 - 数据模型。

与 tests/data/pricing_capture_data.yaml 中的 ui_cases / api_cases 一一对应。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UIPricingCase:
    """UI 模型价格采集用例（页面切换模型，读取价格）。"""
    case_id: str
    model_index: int
    model_name: str
    model_desc: str
    expected_price: Optional[int] = None


@dataclass
class APIPricingCase:
    """API 价格查询用例（直接调用 aiDrawPrice 接口）。"""
    case_id: str
    scenario_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_amount: Optional[int] = None
