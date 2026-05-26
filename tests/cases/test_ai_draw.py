"""
AI 精准渲染 - 知点消耗验证用例

URL: https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=precisionRender

覆盖：
- TC-AIDRAW-001（P0）：选择家装后标准模式消耗 6 知点，切换思考模式后消耗 16 知点

前置：
- 使用 conftest.py 的 ``logged_in_page`` fixture（session 级 storage_state 复用），
  整个会话仅登录一次，后续 test 直接拿到已登录态 page。
"""

import pytest

from common.yaml_loader import load_yaml
from pages.methods.ai_draw_page import AiDrawPage

_DATA_PATH = "tests/data/ai_draw_data.yaml"
_DATA = load_yaml(_DATA_PATH)


def _open_ai_draw_page(page) -> AiDrawPage:
    """已登录前置：直接打开精准渲染页面（含延迟弹窗关闭）。"""
    ai_page = AiDrawPage(page, auto_close_popups=True)
    ai_page.goto()
    return ai_page


class TestAiDraw:
    """AI 精准渲染 - 知点消耗用例集。"""

    # ===== TC-AIDRAW-001 =====
    @pytest.mark.smoke
    @pytest.mark.main
    @pytest.mark.ui
    def test_knowledge_cost_by_mode(self, logged_in_page, assertion):
        """TC-AIDRAW-001（P0）：家装场景下标准/思考模式的知点消耗正确。

        步骤：
          1. 进入精准渲染页面
          2. 点击「家装」分类
          3. 断言生成按钮显示知点数 = expected_cost_standard（6）
          4. 点击「思考模式」切换按钮
          5. 断言生成按钮显示知点数 = expected_cost_thinking（16）
        """
        expected_standard = _DATA["expected_cost_standard"]
        expected_thinking = _DATA["expected_cost_thinking"]

        print(f"=== TC-AIDRAW-001: 家装标准模式期望 {expected_standard} 知点，思考模式期望 {expected_thinking} 知点 ===")

        ai_page = _open_ai_draw_page(logged_in_page)

        # Step 2: 点击家装
        ai_page.click_space_type_home()

        # Step 3: 标准模式知点断言
        cost_standard = ai_page.get_generate_button_cost()
        print(f"标准模式知点数: {cost_standard}")
        assertion.assert_equal(
            cost_standard,
            expected_standard,
            message=f"家装标准模式知点消耗应为 {expected_standard}，实际为 {cost_standard}",
            name="标准模式知点消耗",
        )

        # Step 4: 切换思考模式（点击「标准模式」标签 → 切换为思考模式）
        ai_page.switch_to_thinking_mode()

        # Step 5: 思考模式知点断言
        cost_thinking = ai_page.get_generate_button_cost()
        print(f"思考模式知点数: {cost_thinking}")
        assertion.assert_equal(
            cost_thinking,
            expected_thinking,
            message=f"家装思考模式知点消耗应为 {expected_thinking}，实际为 {cost_thinking}",
            name="思考模式知点消耗",
        )

        print("TC-AIDRAW-001 通过")
