"""
智能生图 - 提示词模板扩充功能 Page Object。

覆盖范围：
- 横幅/气泡提示的展示、关闭、频控
- 输入框引导文案
- 全部模板浮窗的展开/关闭
- 我的模板 / 热门模板 tab 切换
- 搜索模板（输入、防抖、结果验证）
- 新建模板弹窗（表单填写、校验、保存）
- 模板卡片操作（收藏、取消收藏、删除）

URL: https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=agent

元素 YAML：pages/elements/prompt_template_elements.yaml
"""

import time
from typing import List, Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage, PopupStrategy

# ── YAML 键名常量 ─────────────────────────────────────────────────────────
# 横幅
_KEY_BANNER_CONTAINER = "banner_container"
_KEY_BANNER_TAG = "banner_tag"
_KEY_BANNER_TEXT = "banner_text"
_KEY_BANNER_HIGHLIGHT = "banner_highlight"
_KEY_BANNER_BTN_VIEW = "banner_btn_view"
_KEY_BANNER_BTN_GOT_IT = "banner_btn_got_it"

# 气泡
_KEY_BUBBLE_CONTAINER = "bubble_container"
_KEY_BUBBLE_TITLE = "bubble_title"
_KEY_BUBBLE_TEXT = "bubble_text"
_KEY_BUBBLE_BTN_VIEW = "bubble_btn_view"
_KEY_BUBBLE_BTN_GOT_IT = "bubble_btn_got_it"

# 输入框
_KEY_INPUT_TEXTAREA = "input_textarea"
_KEY_INPUT_PLACEHOLDER_AREA = "input_placeholder_area"
_KEY_INPUT_PLACEHOLDER_TEXT = "input_placeholder_text"
_KEY_INPUT_USE_TEMPLATE = "input_use_template"
_KEY_INPUT_BOX = "input_box"

# 全部模板按钮
_KEY_ALL_TEMPLATE_BTN = "all_template_btn"

# 浮窗
_KEY_POPUP_CONTAINER = "popup_container"
_KEY_POPUP_INNER = "popup_inner"
_KEY_POPUP_MENU = "popup_menu"
_KEY_POPUP_MENU_ITEM = "popup_menu_item"
_KEY_POPUP_MENU_ITEM_ACTIVE = "popup_menu_item_active"
_KEY_POPUP_SUBMENU_ITEM = "popup_submenu_item"
_KEY_POPUP_CREATE_BTN = "popup_create_btn"
_KEY_POPUP_CONTENT = "popup_content"
_KEY_POPUP_CONTENT_ITEM = "popup_content_item"
_KEY_POPUP_CLOSE = "popup_close"
_KEY_POPUP_TITLE = "popup_title"

# 搜索
_KEY_SEARCH_BOX = "search_box"
_KEY_SEARCH_INPUT = "search_input"

# 空状态
_KEY_EMPTY_STATE = "empty_state"
_KEY_EMPTY_TITLE = "empty_title"
_KEY_EMPTY_CONTROLS = "empty_controls"
_KEY_PERSONAL_EMPTY_STATE = "personal_empty_state"

# 弹窗
_KEY_MODAL_CONTAINER = "modal_container"
_KEY_MODAL_CLOSE = "modal_close"
_KEY_MODAL_BODY = "modal_body"

# 登录弹窗
_KEY_LOGIN_MODAL = "login_modal"

# 卡片操作
_KEY_CARD_FAVORITE_BTN = "card_favorite_btn"
_KEY_CARD_DELETE_BTN = "card_delete_btn"
_KEY_CARD_ACTION_MASK = "card_action_mask"

# Toast
_KEY_TOAST = "toast"

# 确认弹窗
_KEY_CONFIRM_MODAL = "confirm_modal"
_KEY_CONFIRM_OK_BTN = "confirm_ok_btn"
_KEY_CONFIRM_CANCEL_BTN = "confirm_cancel_btn"


class PromptTemplatePage(BasePage):
    """智能生图提示词模板扩充功能页面操作类。"""

    DEFAULT_URL = "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=agent"

    def __init__(self, page: Page, auto_close_popups: bool = False) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/prompt_template_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    def extra_popup_strategies(self) -> List[PopupStrategy]:
        """处理 AI 绘图页特有的延迟弹窗。"""
        return [
            PopupStrategy(
                name="ai_draw_banana_guide_modal",
                trigger_selector="[class*='aiDrawAdForPluginModal']",
                close_selector="[class*='leftBtn'], .ant-modal-close, [class*='closeIcon'], [class*='CloseIcon']",
            ),
        ]

    # ===== 页面导航 =====

    def goto(self, url: Optional[str] = None, close_popups_after_load: bool = True) -> None:
        """进入智能生图页面（menuKey=agent）。"""
        super().goto(
            url or self.DEFAULT_URL,
            close_popups_after_load=close_popups_after_load,
        )
        self.page.wait_for_timeout(3000)
        self.close_all_popups(max_tries=3)
        # 兜底：移除残留弹窗
        self.page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.body.classList.remove('ant-scrolling-effect');
            document.body.style.overflow = '';
        }""")
        self.page.wait_for_timeout(500)

    # ===== 横幅提示 =====

    def is_banner_visible(self, timeout: int = 3000) -> bool:
        """判断横幅是否可见。"""
        try:
            return self.get_locator(_KEY_BANNER_CONTAINER).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def get_banner_text(self) -> str:
        """获取横幅完整文本。"""
        tag = self.get_locator(_KEY_BANNER_TAG).first
        text_el = self.get_locator(_KEY_BANNER_TEXT).first
        highlight = self.get_locator(_KEY_BANNER_HIGHLIGHT).first
        parts = []
        if tag.is_visible(timeout=1000):
            parts.append(tag.inner_text().strip())
        if text_el.is_visible(timeout=1000):
            parts.append(text_el.inner_text().strip())
        if highlight.is_visible(timeout=1000):
            parts.append(highlight.inner_text().strip())
        return " ".join(parts)

    def click_banner_view(self) -> None:
        """点击横幅'查看'按钮 → 关闭横幅 + 展开全部模板。"""
        btn = self.get_locator(_KEY_BANNER_BTN_VIEW).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def click_banner_got_it(self) -> None:
        """点击横幅'知道了'按钮 → 关闭横幅。"""
        btn = self.get_locator(_KEY_BANNER_BTN_GOT_IT).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1000)

    # ===== 气泡提示 =====

    def is_bubble_visible(self, timeout: int = 3000) -> bool:
        """判断气泡是否可见。"""
        try:
            return self.get_locator(_KEY_BUBBLE_CONTAINER).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def get_bubble_title(self) -> str:
        """获取气泡标题。"""
        el = self.get_locator(_KEY_BUBBLE_TITLE).first
        el.wait_for(state="visible", timeout=5000)
        return el.inner_text().strip()

    def get_bubble_text(self) -> str:
        """获取气泡正文。"""
        el = self.get_locator(_KEY_BUBBLE_TEXT).first
        el.wait_for(state="visible", timeout=5000)
        return el.inner_text().strip()

    def click_bubble_view(self) -> None:
        """点击气泡'查看'按钮 → 关闭气泡 + 展开全部模板。"""
        btn = self.get_locator(_KEY_BUBBLE_BTN_VIEW).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def click_bubble_got_it(self) -> None:
        """点击气泡'知道了'按钮 → 关闭气泡。"""
        btn = self.get_locator(_KEY_BUBBLE_BTN_GOT_IT).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1000)

    # ===== 输入框 =====

    def get_input_placeholder(self) -> str:
        """获取输入框引导文案。"""
        el = self.get_locator(_KEY_INPUT_PLACEHOLDER_TEXT).first
        if el.is_visible(timeout=3000):
            return el.inner_text().strip()
        return ""

    def is_placeholder_visible(self, timeout: int = 2000) -> bool:
        """判断引导文案是否可见。"""
        try:
            return self.get_locator(_KEY_INPUT_PLACEHOLDER_TEXT).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def is_use_template_visible(self, timeout: int = 2000) -> bool:
        """判断'使用模板 →'是否可见。"""
        try:
            return self.get_locator(_KEY_INPUT_USE_TEMPLATE).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def click_use_template(self) -> None:
        """点击'使用模板 →'展开全部模板浮窗。"""
        btn = self.get_locator(_KEY_INPUT_USE_TEMPLATE).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def type_in_input(self, text: str) -> None:
        """在输入框中输入文本。"""
        textarea = self.get_locator(_KEY_INPUT_TEXTAREA).first
        textarea.wait_for(state="visible", timeout=5000)
        textarea.click()
        textarea.fill(text)
        self.page.wait_for_timeout(300)

    def clear_input(self) -> None:
        """清空输入框。"""
        textarea = self.get_locator(_KEY_INPUT_TEXTAREA).first
        textarea.wait_for(state="visible", timeout=5000)
        textarea.fill("")
        self.page.wait_for_timeout(300)

    def get_input_text(self) -> str:
        """获取输入框当前文本。"""
        textarea = self.get_locator(_KEY_INPUT_TEXTAREA).first
        return textarea.input_value()

    # ===== 全部模板浮窗 =====

    def click_all_template_btn(self) -> None:
        """点击'全部模板'按钮展开浮窗。"""
        btn = self.get_locator(_KEY_ALL_TEMPLATE_BTN).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def is_popup_visible(self, timeout: int = 3000) -> bool:
        """判断浮窗是否可见。"""
        try:
            return self.get_locator(_KEY_POPUP_CONTAINER).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def close_popup(self) -> None:
        """关闭浮窗。"""
        close = self.get_locator(_KEY_POPUP_CLOSE).first
        if close.is_visible(timeout=2000):
            close.click()
            self.page.wait_for_timeout(800)

    def get_popup_title(self) -> str:
        """获取浮窗标题文本。"""
        el = self.get_locator(_KEY_POPUP_TITLE).first
        if el.is_visible(timeout=2000):
            return el.inner_text().strip()
        return ""

    # ===== 左侧菜单 =====

    def get_menu_items(self) -> List[str]:
        """获取左侧菜单所有可见项文本。"""
        items = self.get_locator(_KEY_POPUP_MENU_ITEM)
        result = []
        for i in range(items.count()):
            el = items.nth(i)
            if el.is_visible(timeout=500):
                text = el.inner_text().strip()
                if text:
                    result.append(text)
        return result

    def click_menu_item(self, text: str) -> None:
        """点击左侧菜单中指定文本的菜单项。"""
        items = self.get_locator(_KEY_POPUP_MENU_ITEM)
        for i in range(items.count()):
            el = items.nth(i)
            if el.is_visible(timeout=500) and text in el.inner_text():
                el.click()
                self.page.wait_for_timeout(1000)
                return
        raise ValueError(f"未找到菜单项: {text}")

    def get_active_menu_item_text(self) -> str:
        """获取当前激活的菜单项文本。"""
        el = self.get_locator(_KEY_POPUP_MENU_ITEM_ACTIVE).first
        if el.is_visible(timeout=2000):
            return el.inner_text().strip()
        return ""

    # ===== 搜索 =====

    def is_search_visible(self, timeout: int = 2000) -> bool:
        """判断搜索框是否可见。"""
        try:
            return self.get_locator(_KEY_SEARCH_INPUT).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def get_search_placeholder(self) -> str:
        """获取搜索框引导文案。"""
        el = self.get_locator(_KEY_SEARCH_INPUT).first
        return el.get_attribute("placeholder") or ""

    def search(self, keyword: str, wait_debounce: bool = True) -> None:
        """在搜索框输入关键词并触发搜索。

        :param keyword: 搜索关键词
        :param wait_debounce: 是否等待 300ms 防抖
        """
        search_input = self.get_locator(_KEY_SEARCH_INPUT).first
        search_input.wait_for(state="visible", timeout=5000)
        search_input.click()
        search_input.fill(keyword)
        if wait_debounce:
            self.page.wait_for_timeout(400)  # 300ms 防抖 + 100ms buffer

    def clear_search(self) -> None:
        """清空搜索框。"""
        search_input = self.get_locator(_KEY_SEARCH_INPUT).first
        search_input.fill("")
        self.page.wait_for_timeout(300)

    def get_search_results(self) -> List[str]:
        """获取搜索结果中的模板名称列表。"""
        items = self.get_locator(_KEY_POPUP_CONTENT_ITEM)
        results = []
        for i in range(items.count()):
            el = items.nth(i)
            if el.is_visible(timeout=500):
                text = el.inner_text().strip()
                if text:
                    results.append(text)
        return results

    def get_search_result_count(self) -> int:
        """获取搜索结果数量。"""
        return self.get_locator(_KEY_POPUP_CONTENT_ITEM).count()

    # ===== 模板卡片操作 =====

    def get_template_cards(self) -> Locator:
        """获取所有模板卡片。"""
        return self.get_locator(_KEY_POPUP_CONTENT_ITEM)

    def get_template_card_count(self) -> int:
        """获取模板卡片数量。"""
        return self.get_locator(_KEY_POPUP_CONTENT_ITEM).count()

    def hover_template_card(self, index: int = 0) -> None:
        """hover 指定索引的模板卡片。"""
        card = self.get_locator(_KEY_POPUP_CONTENT_ITEM).nth(index)
        card.wait_for(state="visible", timeout=5000)
        card.hover()
        self.page.wait_for_timeout(500)

    def get_template_name(self, index: int = 0) -> str:
        """获取指定索引模板卡片的名称。"""
        card = self.get_locator(_KEY_POPUP_CONTENT_ITEM).nth(index)
        # 模板名称通常在卡片的标题元素中
        try:
            title = card.locator("[class*='title'], [class*='Title'], [class*='name'], [class*='Name']").first
            if title.is_visible(timeout=1000):
                return title.inner_text().strip()
        except Exception:
            pass
        return card.inner_text().strip()

    def is_favorite_btn_visible(self, timeout: int = 1000) -> bool:
        """判断收藏按钮是否可见（hover 后）。"""
        try:
            return self.get_locator(_KEY_CARD_FAVORITE_BTN).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def click_favorite(self) -> None:
        """点击收藏按钮。"""
        btn = self.get_locator(_KEY_CARD_FAVORITE_BTN).first
        btn.wait_for(state="visible", timeout=3000)
        btn.click()
        self.page.wait_for_timeout(1000)

    def is_delete_btn_visible(self, timeout: int = 1000) -> bool:
        """判断删除按钮是否可见（hover 后）。"""
        try:
            return self.get_locator(_KEY_CARD_DELETE_BTN).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def click_delete(self) -> None:
        """点击删除按钮。"""
        btn = self.get_locator(_KEY_CARD_DELETE_BTN).first
        btn.wait_for(state="visible", timeout=3000)
        btn.click()
        self.page.wait_for_timeout(500)

    # ===== 确认弹窗 =====

    def is_confirm_modal_visible(self, timeout: int = 3000) -> bool:
        """判断确认弹窗是否可见。"""
        try:
            return self.get_locator(_KEY_CONFIRM_MODAL).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def confirm_ok(self) -> None:
        """点击确认弹窗的'确认'按钮。"""
        btn = self.get_locator(_KEY_CONFIRM_OK_BTN).first
        btn.wait_for(state="visible", timeout=3000)
        btn.click()
        self.page.wait_for_timeout(1000)

    def confirm_cancel(self) -> None:
        """点击确认弹窗的'取消'按钮。"""
        btn = self.get_locator(_KEY_CONFIRM_CANCEL_BTN).first
        btn.wait_for(state="visible", timeout=3000)
        btn.click()
        self.page.wait_for_timeout(500)

    # ===== 新建模板弹窗 =====

    def click_create_template(self) -> None:
        """点击'新建模板'按钮。"""
        btn = self.get_locator(_KEY_POPUP_CREATE_BTN).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def is_create_modal_visible(self, timeout: int = 3000) -> bool:
        """判断新建模板弹窗是否可见。"""
        try:
            modal = self.get_locator(_KEY_MODAL_CONTAINER).first
            return modal.is_visible(timeout=timeout)
        except Exception:
            return False

    def is_login_modal_visible(self, timeout: int = 3000) -> bool:
        """判断登录弹窗是否可见。"""
        try:
            return self.get_locator(_KEY_LOGIN_MODAL).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def close_modal(self) -> None:
        """关闭当前弹窗。"""
        close = self.get_locator(_KEY_MODAL_CLOSE).first
        if close.is_visible(timeout=2000):
            close.click()
            self.page.wait_for_timeout(500)

    def get_modal_body_text(self) -> str:
        """获取弹窗 body 文本。"""
        body = self.get_locator(_KEY_MODAL_BODY).first
        if body.is_visible(timeout=2000):
            return body.inner_text().strip()
        return ""

    # ===== Toast =====

    def get_toast_text(self, timeout: int = 3000) -> str:
        """获取 toast 提示文本。"""
        try:
            toast = self.page.locator(".ant-message-notice").first
            toast.wait_for(state="visible", timeout=timeout)
            self.page.wait_for_timeout(300)
            return toast.inner_text().strip()
        except PlaywrightTimeoutError:
            return ""

    def wait_for_toast(self, expected_text: str = "", timeout: int = 5000) -> str:
        """等待 toast 出现并返回文本。"""
        self.page.wait_for_selector(".ant-message-notice", state="visible", timeout=timeout)
        self.page.wait_for_timeout(500)
        toasts = self.page.locator(".ant-message-notice")
        for i in range(toasts.count()):
            text = toasts.nth(i).inner_text().strip()
            if not expected_text or expected_text in text:
                return text
        return ""

    # ===== 空状态 =====

    def is_empty_state_visible(self, timeout: int = 2000) -> bool:
        """判断'我的模板'空状态是否可见。"""
        try:
            return self.get_locator(_KEY_EMPTY_STATE).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def get_empty_state_text(self) -> str:
        """获取空状态文本。"""
        el = self.get_locator(_KEY_EMPTY_TITLE).first
        if el.is_visible(timeout=2000):
            return el.inner_text().strip()
        return ""

    # ===== 工具方法 =====

    def dismiss_banner_or_bubble(self) -> str:
        """关闭当前展示的横幅或气泡，返回关闭的类型。

        Returns:
            "banner" | "bubble" | "none"
        """
        if self.is_banner_visible(timeout=1000):
            self.click_banner_view()
            return "banner"
        elif self.is_bubble_visible(timeout=1000):
            self.click_bubble_view()
            return "bubble"
        return "none"

    def ensure_popup_open(self) -> None:
        """确保浮窗已展开。如果未展开则尝试展开。"""
        if self.is_popup_visible(timeout=1000):
            return
        # 先尝试关闭横幅/气泡
        self.dismiss_banner_or_bubble()
        if not self.is_popup_visible(timeout=1000):
            # 尝试点击全部模板按钮
            try:
                self.click_all_template_btn()
            except Exception:
                pass

    def reset_template_popup_state(self) -> None:
        """重置模板浮窗状态（清除 localStorage 中的频控记录）。"""
        self.page.evaluate("""() => {
            // 清除可能的频控记录
            const keys = Object.keys(localStorage);
            for (const key of keys) {
                if (key.toLowerCase().includes('template') || key.toLowerCase().includes('bubble') || key.toLowerCase().includes('banner') || key.toLowerCase().includes('upgrade')) {
                    localStorage.removeItem(key);
                }
            }
        }""")
        self.page.wait_for_timeout(300)
