# -*- coding: utf-8 -*-
"""精准渲染定价采集 - 数据模型。

与 tests/data/precision_render_pricing_data.yaml 中的 ui_cases / api_cases 一一对应。

页面结构：
  精准渲染 (menuKey=precisionRender) 有 3 种 DeepMode
  创作渲染 (menuKey=ideaRender)      无 DeepMode
  效果图美化 (menuKey=imageEnhancement) 无 DeepMode
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UIPricingCase:
    """UI 创作模式×子模式 价格采集用例。

    deep_mode_index 为 -1 表示该创作模式无 DeepMode（仅通过 modeText popover 切换子模式）。
    sub_mode_name 用于创作渲染/效果图美的子模式名称（"标准模式" / "Nano Banana Pro"）。
    """
    case_id: str
    creation_mode_index: int
    creation_mode_name: str
    deep_mode_index: int
    deep_mode_name: str
    expected_price: Optional[int] = None
    sub_mode_name: Optional[str] = None


@dataclass
class APIPricingCase:
    """API 价格查询用例（直接调用 aiDrawPrice 接口）。"""
    case_id: str
    scenario_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_amount: Optional[int] = None
