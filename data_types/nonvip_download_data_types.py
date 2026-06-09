"""非VIP下载弹窗计费逻辑修复 - 参数化用例数据类型。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CouponPriorityCase:
    """AUTO-DFT-006 参数化数据：券优先级排序验证用例。

    字段:
        case_id         用例编号，如 "DFT-006-a"
        scenario_name   场景描述，如 "40+5组合默认选40知币"
        coupon_combo    账号持有的券组合，如 "40+5" / "35+5"
        expected_selected 期望默认选中的面额字符串，如 "40" / "35"
    """

    case_id: str
    scenario_name: str
    coupon_combo: str
    expected_selected: str
