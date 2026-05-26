from dataclasses import dataclass


@dataclass(frozen=True)
class PrecisionRenderCaseData:
    """
    精准渲染 - 氛围切换用例数据。

    与 tests/data/precision_render_data.yaml 中 cases 列表一一对应。
    """
    case_name: str
    case_id: str             # 例如 "TC-ATM-008"
    target_atmosphere: str   # 目标氛围：默认 / 氛围光影 / 明亮通透 / 夜景
    initial_atmosphere: str = "默认"  # 用例开始时已选中的氛围（用于反向断言）
