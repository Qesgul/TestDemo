# -*- coding: utf-8 -*-
"""AI 定价采集 - 数据模型（平面填彩 / 实景改造 / 全景渲染）。

与 tests/data/ai_pricing_data.yaml 中的 ui_cases / api_cases 一一对应。
页面结构与创作渲染/效果图美化相同：BottomPartButtons 模式切换。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AIPricingUICase:
    """UI 子模式价格采集用例。

    product_name: 产品名称（"平面填彩" / "实景改造" / "全景渲染"）
    menu_key: URL 参数值（"floorPlanColor" / "insituRenovation" / "panoramicRender"）
    sub_mode_name: 子模式名称（"标准模式" / "Nano Banana Pro" / "GPT Image 2"）
    navigate_via_menu: True 则从左侧菜单进入（全景渲染需此方式）
    """
    case_id: str
    product_name: str
    menu_key: str
    sub_mode_name: str
    expected_price: Optional[int] = None
    navigate_via_menu: bool = False


@dataclass
class AIPricingAPICase:
    """API 价格查询用例（直接调用 aiDrawPrice 接口）。"""
    case_id: str
    scenario_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_amount: Optional[int] = None
