"""
AI 精准渲染页面 Page Object（上传→选择→生成流程）。

覆盖范围：
- 上传截图（action=upload，通过 set_input_files 注入，不触发 OS 文件选择器）
- 空间类型「家装」按钮点击
- 「生成」按钮点击（含知点数量，selector 稳定）
- 思考模式 / 标准模式切换按钮点击

URL: https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=precisionRender

元素 YAML：pages/elements/ai_draw_elements.yaml
  - 所有 selector 均经 ai-selector skill + 人工点选确认

注意：
  本 Page 专注"上传→生成"流程。
  氛围设置 / 空间类型完整性校验等功能由 PrecisionRenderPage 负责，避免重复。
"""

import re
from typing import List, Optional

from playwright.sync_api import Page

from pages.base_page import BasePage, PopupStrategy

# ── YAML 键名常量（与 ai_draw_elements.yaml 一一对应）────────────────────────
# 键名含中文引号及全角括号，用常量集中维护，避免散落在方法体里出错。
_KEY_UPLOAD = 'step1_"上传截图"按钮或上传图片的触发区域'
_KEY_SPACE_HOME = 'step2_"家装"分类按钮'
_KEY_GENERATE = 'step3_"生成"按钮（按钮文本中包含知点数量）'
_KEY_THINK_MODE = 'step4_生成按钮旁边的"思考模式"切换按钮或开关'
_KEY_SWITCH_TO_THINKING = "thinking_mode_switch_from_standard"
_KEY_THINKING_PANEL_OPTION = "thinking_mode_panel_thinking_option"


class AiDrawPage(BasePage):
    """AI 精准渲染页面操作类（上传截图 → 选择分类 → 触发生成）。"""

    # 页面入口 URL：唯一配置点（不在 yaml / test 中重复维护）
    DEFAULT_URL = "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=precisionRender"

    def __init__(self, page: Page, auto_close_popups: bool = False) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/ai_draw_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        """处理 AI 绘图页特有的延迟弹窗。

        AIDrawBananaGuideModal：广告引导弹窗，页面加载后约 1-2 秒出现，
        会遮挡操作区域按钮。该弹窗使用自定义按钮（leftBtn / rightBtn），
        无标准 .ant-modal-close，需单独处理。

        关闭优先级：
          1. leftBtn（通常是「跳过」）
          2. ant-modal-close（标准关闭图标，作为兜底）
          3. 其他常见关闭 class
        """
        return [
            # 主容器：class 含 aiDrawAdForPluginModal（从 ant-modal-wrap 到内容区）
            # leftBtn 通常是「跳过」；closeIcon 是标准关闭图标兜底
            PopupStrategy(
                name="ai_draw_banana_guide_modal",
                trigger_selector="[class*='aiDrawAdForPluginModal']",
                close_selector="[class*='leftBtn'], .ant-modal-close, [class*='closeIcon'], [class*='CloseIcon']",
            ),
        ]

    # ===== 页面导航 =====

    def goto(
        self,
        url: Optional[str] = None,
        close_popups_after_load: bool = True,
        wait_state: str = "domcontentloaded",
    ) -> None:
        """进入精准渲染页面。

        默认跳转到 DEFAULT_URL；切换测试环境时传入 url 覆盖。
        父类 goto 会先 reload 一次关弹窗，本页再用 wait 3s + close_all_popups
        + JS evaluate 兜底处理延迟出现的引导弹窗。
        """
        super().goto(
            url or self.DEFAULT_URL,
            close_popups_after_load=close_popups_after_load,
            wait_state=wait_state,
        )
        # 延迟弹窗（如 AIDrawBananaGuideModal）通常在页面渲染完成 1~2s 后出现
        self.page.wait_for_timeout(3000)
        self.close_all_popups(max_tries=3)
        # 兜底：用 JS 直接移除所有仍在 DOM 中的模态遮罩和 body overflow 锁定，
        # 应对 close_all_popups 无法关闭的复杂交互式引导弹窗。
        self.page.evaluate("""() => {
            // 移除所有 ant-modal-wrap（模态遮罩层）
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            // 移除 ant-modal-root 中的残留（如有）
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            // 解锁 body 滚动（ant-scrolling-effect 锁定）
            document.body.classList.remove('ant-scrolling-effect');
            document.body.style.overflow = '';
        }""")
        self.page.wait_for_timeout(300)

    # ===== 上传截图 =====

    def upload_screenshot(self, file_path: str) -> None:
        """上传截图文件。

        元素 action=upload，必须用 set_input_files() 注入路径，
        不能使用 click()——headless 模式下 click 不会弹 OS 文件选择器。

        :param file_path: 本地图片路径，例如 "tests/assets/sample_screenshot.jpg"
        """
        locator = self.get_locator(_KEY_UPLOAD).first
        locator.wait_for(state="attached", timeout=10_000)
        locator.set_input_files(file_path)

    # ===== 空间类型 =====

    def click_space_type_home(self) -> None:
        """点击「家装」空间类型分类按钮。"""
        btn = self.get_locator(_KEY_SPACE_HOME).first
        btn.wait_for(state="visible", timeout=10_000)
        btn.click()

    def is_space_type_home_visible(self) -> bool:
        """判断「家装」按钮是否可见。"""
        try:
            return self.get_locator(_KEY_SPACE_HOME).first.is_visible(timeout=5_000)
        except Exception:
            return False

    # ===== 生成按钮 =====

    def click_generate(self) -> None:
        """点击「生成」按钮（CSS 稳定定位，规避按钮文本含动态知点数字）。"""
        btn = self.get_locator(_KEY_GENERATE).first
        btn.wait_for(state="visible", timeout=10_000)
        btn.click()

    def is_generate_button_visible(self) -> bool:
        """判断「生成」按钮是否可见。"""
        try:
            return self.get_locator(_KEY_GENERATE).first.is_visible(timeout=5_000)
        except Exception:
            return False

    def get_generate_button_cost(self) -> int:
        """从「生成」按钮文本中提取当前操作所需知点数。

        按钮文本格式为「{数字}生成」，例如「6生成」「16生成」。
        提取并返回前缀整数；若无法解析则抛出 ValueError。
        """
        btn = self.get_locator(_KEY_GENERATE).first
        btn.wait_for(state="visible", timeout=10_000)
        text = btn.inner_text().strip()
        m = re.search(r"\d+", text)
        if m is None:
            raise ValueError(
                f"无法从生成按钮文本中提取知点数量，实际文本: {text!r}"
            )
        return int(m.group())

    # ===== 模式切换 =====

    def click_thinking_mode_toggle(self) -> None:
        """点击「思考模式」切换按钮（标准 ⇄ 思考）。

        注：切换文案会在「标准模式」和「思考模式」之间变化；
        selector 使用 CSS 父容器路径，规避动态文本不稳定问题。
        点击后等待 1s，确保生成按钮文本（知点数）已完成更新。
        """
        btn = self.get_locator(_KEY_THINK_MODE).first
        btn.wait_for(state="visible", timeout=10_000)
        btn.click()
        # 等待 UI 响应：模式切换后生成按钮的知点数会异步刷新
        self.page.wait_for_timeout(1000)

    def is_thinking_mode_toggle_visible(self) -> bool:
        """判断「思考模式」切换按钮是否可见。"""
        try:
            return self.get_locator(_KEY_THINK_MODE).first.is_visible(timeout=5_000)
        except Exception:
            return False

    def switch_to_thinking_mode(self) -> None:
        """从标准模式切换到思考模式（两步流程）。

        步骤1：点击 DeepMode wrapper 打开模式选择面板（面板从按钮上方弹出）。
        步骤2：在面板中点击「思考模式」选项（modeTitle 精确文本匹配）。
        点击后等待 1.5s，确保生成按钮知点数完成异步刷新。
        """
        # 步骤1：打开模式选择面板
        wrapper = self.get_locator(_KEY_SWITCH_TO_THINKING).first
        wrapper.wait_for(state="visible", timeout=10_000)
        wrapper.click()
        self.page.wait_for_timeout(800)

        # 步骤2：在面板中选择「思考模式」
        option = self.get_locator(_KEY_THINKING_PANEL_OPTION).first
        option.wait_for(state="visible", timeout=8_000)
        option.click()
        self.page.wait_for_timeout(1500)
