# -*- coding: utf-8 -*-
"""下载确认弹窗 AB 实验 - 参数化用例数据模型。

与 tests/data/download_ab_data.yaml 中的 cases / price_scenarios 一一对应。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExpModalForm:
    """实验组弹窗形态（VIP × 券 组合），用于 EXP-017~020 参数化。"""
    case_id: str
    scenario_name: str
    is_vip: bool
    has_coupon: bool
    expect_vip_row: bool        # 期望展示"VIP立减"行
    expect_coupon_row: bool     # 期望展示"下载抵扣券"行
    expect_promo: bool          # 期望出现搭售区（实验组恒 False）
    account_key: str            # "vip" / "nonvip"，决定所需登录账号


@dataclass
class PriceScenario:
    """详情页到手价 == 弹窗默认金额 一致性多场景（EXP-003）。"""
    case_id: str
    scenario_name: str
    material_url: str           # 各类素材详情页 URL（提测后回填，TODO 前缀表示未就绪）


@dataclass
class CtrlModalForm:
    """对照组弹窗形态（对应 PRD 图1/2/3），用于 CTRL-002~004 参数化。"""
    case_id: str
    scenario_name: str
    is_vip: bool
    has_coupon: bool
    expect_promo: bool          # 对照组恒 True
    expect_vip_pending: bool    # 是否期望"待激活"标签（图2）
    account_key: str
    figure_ref: str = ""        # 对应 PRD 图号，便于追溯
