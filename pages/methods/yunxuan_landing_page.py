"""知末云渲染落地页 - Page Object

URL: https://www.znzmo.com/yunxuanLanding.html?fromwhere=0
需求: 3D云渲染落地页优化PRD ｜ 用例: 07_automation_test_cases.md

选择器一律经 self.get_locator(yaml_key) 读取，不在方法体内硬编码 CSS/XPath。
"""
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator
from playwright.sync_api import Page

from pages.base_page import BasePage

_logger = logging.getLogger(__name__)


class YunxuanLandingPage(BasePage):
    """知末云渲染落地页。"""

    # 唯一 URL 配置点（导航入口不写进 yaml / 不暴露到用例层）
    DEFAULT_URL = "https://www.znzmo.com/yunxuanLanding.html?fromwhere=0"

    def __init__(self, page: Page, auto_close_popups: bool = False) -> None:
        super().__init__(
            page,
            "pages/elements/yunxuan_landing_elements.yaml",
            auto_close_popups,
        )

    def goto(self, url: Optional[str] = None, **kwargs) -> None:
        """打开落地页。未显式传 url 时用 DEFAULT_URL。"""
        super().goto(url or self.DEFAULT_URL, **kwargs)

    # ===== 元素定位方法（从 YAML 读取） =====
    def bottom_banner(self) -> Locator:
        return self.get_locator("bottom_banner")

    def bottom_banner_cta(self) -> Locator:
        return self.get_locator("bottom_banner_cta")

    def first_screen(self) -> Locator:
        return self.get_locator("first_screen")

    # ===== 滚动 / 状态动作方法 =====
    def scroll_to_top(self) -> None:
        """滚动回页面顶部（首屏置顶）。"""
        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(500)

    def scroll_by_viewport(self, factor: float = 1.0) -> None:
        """向下滚动 factor 个视口高度。"""
        self.page.evaluate(
            "(f) => window.scrollBy(0, window.innerHeight * f)", factor
        )
        self.page.wait_for_timeout(500)

    def scroll_to_y(self, y: int) -> None:
        """滚动到指定纵向像素位置。"""
        self.page.evaluate("(y) => window.scrollTo(0, y)", y)
        self.page.wait_for_timeout(300)

    def leave_first_screen(self) -> None:
        """下滑离开首屏（触发底部 banner 吸底展示）。"""
        self.scroll_by_viewport(1.2)

    def get_bottom_banner_text(self) -> str:
        """读取底部 banner 文案（去空白）。"""
        try:
            txt = self.bottom_banner().inner_text(timeout=5000)
        except Exception:
            txt = ""
        return (txt or "").strip()

    def is_bottom_banner_visible(self) -> bool:
        """底部 banner 当前是否"真正吸底可见"。

        .ylStickyBar 为 position:fixed，靠 transform translateY + modifier class
        切换显隐，display/visibility/opacity 始终正常：
        - 首屏置顶：仅 class ``ylStickyBar``，``translateY(70px)`` 推到视口下方（屏外）。
        - 下滑后：追加 ``ylStickyBar--visible`` 且 ``translateY(0)`` 进入视口。

        因此 Playwright ``is_visible()`` 恒为 True（不感知 transform 平移），
        基于元素 rect 的"是否在视口内"又会在 ``top == innerHeight`` 边界 off-by-one。
        页面自身的状态机 class ``ylStickyBar--visible`` 才是最可靠的显隐信号，
        故以该 class 作为判定依据。
        """
        try:
            return bool(self.bottom_banner().evaluate(
                "(el) => el.classList.contains('ylStickyBar--visible')"
            ))
        except Exception:
            return False

    def sample_banner_visibility_around_threshold(
        self,
        center_y: int = 700,
        delta: int = 40,
        rounds: int = 6,
    ) -> List[bool]:
        """在临界滚动点上下少量像素反复采样 banner 可见性（TC-AT-007）。

        在 center_y±delta 之间来回滚动 rounds 轮，每轮记录一次 banner 可见性。
        返回可见性布尔列表，供用例判断"临界处状态是否稳定"。
        """
        samples: List[bool] = []
        for i in range(rounds):
            y = center_y + (delta if i % 2 == 0 else -delta)
            self.scroll_to_y(y)
            samples.append(self.is_bottom_banner_visible())
        return samples

    def banner_visibility_through_screens(self, steps: int = 6) -> List[bool]:
        """从当前位置分 steps 步滚动到页面底部，记录每步 banner 可见性（TC-AT-008）。"""
        result: List[bool] = []
        total = self.page.evaluate(
            "Math.max(document.body.scrollHeight - window.innerHeight, 0)"
        )
        for i in range(1, steps + 1):
            self.scroll_to_y(int(total * i / steps))
            result.append(self.is_bottom_banner_visible())
        return result

    # ═══════════════════════════════════════════════════════
    # 以下：各模块元素定位 & 动作方法（按用例文档模块顺序追加）
    # ═══════════════════════════════════════════════════════

    # ── 导航/顶部栏 ─────────────────────────────────────────
    def top_nav(self) -> Locator:
        return self.get_locator("top_nav")

    def nav_logo(self) -> Locator:
        return self.get_locator("nav_logo")

    def nav_download_btn(self) -> Locator:
        return self.get_locator("nav_download_btn")

    def count_nav_links(self) -> int:
        """统计顶部栏内导航链接数量（排除 logo/CTA）。"""
        return self.top_nav().locator("a:not(.ylNavLogoMark):not(.ylNavCta), button:not(.ylNavCta)").count()

    # ── 首屏 / 轮播 ─────────────────────────────────────────
    def screen1(self) -> Locator:
        return self.get_locator("first_screen")

    def screen1_heading(self) -> Locator:
        return self.get_locator("screen1_heading")

    def screen1_cta_btn(self) -> Locator:
        return self.get_locator("screen1_cta_btn")

    def carousel_prev(self) -> Locator:
        return self.get_locator("carousel_prev")

    def carousel_next(self) -> Locator:
        return self.get_locator("carousel_next")

    def carousel_dots(self) -> Locator:
        return self.get_locator("carousel_dots")

    def carousel_dot_active(self) -> Locator:
        return self.get_locator("carousel_dot_active")

    def carousel_slide_active(self) -> Locator:
        return self.get_locator("carousel_slide_active")

    def get_active_slide_index(self) -> int:
        """返回当前激活轮播图的索引（0-based）。"""
        dots = self.carousel_dots()
        count = dots.count()
        for i in range(count):
            cls = dots.nth(i).get_attribute("class") or ""
            if "active" in cls:
                return i
        return -1

    def scroll_to_element(self, locator: Locator) -> None:
        """将元素滚动到视口内。"""
        locator.scroll_into_view_if_needed()
        self.page.wait_for_timeout(400)

    def get_scroll_y(self) -> int:
        return int(self.page.evaluate("window.scrollY"))

    def is_in_viewport(self, locator: Locator) -> bool:
        """判断元素是否在视口内。"""
        return bool(locator.evaluate(
            "(el) => { const r=el.getBoundingClientRect();"
            " return r.top < window.innerHeight && r.bottom > 0 && r.left < window.innerWidth && r.right > 0; }"
        ))

    # ── 第二屏 ─────────────────────────────────────────────
    def s2_cards_container(self) -> Locator:
        return self.get_locator("s2_cards_container")

    def s2_cards(self) -> Locator:
        return self.get_locator("s2_card")

    def s2_link_workflow(self) -> Locator:
        return self.get_locator("s2_link_workflow")

    def s2_link_reviews(self) -> Locator:
        return self.get_locator("s2_link_reviews")

    def s2_link_cases(self) -> Locator:
        return self.get_locator("s2_link_cases")

    def s2_welfare_btn(self) -> Locator:
        return self.get_locator("s2_welfare_btn")

    def click_s2_welfare_btn(self) -> None:
        """点击"立即领取福利"展开选项卡。"""
        self.s2_welfare_btn().click()
        self.page.wait_for_timeout(400)

    def get_welfare_option_buttons(self) -> List[Locator]:
        """展开后的福利选项按钮列表（文案匹配）。"""
        opts = []
        for text in ["领取30天免费渲", "领免费VIP"]:
            loc = self.page.get_by_role("button", name=re.compile(text))
            opts.append(loc)
        return opts

    def scroll_to_screen(self, screen_id: str) -> None:
        """跳转到指定锚点屏（如 '#yl-workflow'）。"""
        self.page.evaluate(
            f"const el=document.querySelector('{screen_id}'); if(el) el.scrollIntoView();"
        )
        self.page.wait_for_timeout(600)

    # ── 第三屏 ─────────────────────────────────────────────
    def screen3(self) -> Locator:
        return self.get_locator("screen3")

    def s3_step_cards(self) -> Locator:
        return self.get_locator("s3_step_card")

    def s3_download_btn(self) -> Locator:
        return self.get_locator("s3_download_btn")

    def get_step_card_titles(self) -> List[str]:
        """返回各流程卡片的标题文本列表。"""
        count = self.s3_step_cards().count()
        titles = []
        for i in range(count):
            h = self.s3_step_cards().nth(i).locator("h3")
            if h.count() > 0:
                titles.append(h.inner_text().strip())
        return titles

    # ── 第四屏 ─────────────────────────────────────────────
    def screen4(self) -> Locator:
        return self.get_locator("screen4")

    def s4_category_tabs(self) -> Locator:
        return self.get_locator("s4_category_tab")

    def s4_active_tab(self) -> Locator:
        return self.get_locator("s4_category_tab_active")

    def s4_case_imgs(self) -> Locator:
        return self.get_locator("s4_case_img")

    def s4_case_cards(self) -> Locator:
        return self.get_locator("s4_case_card")

    def s4_download_btn(self) -> Locator:
        return self.get_locator("s4_download_btn")

    def click_category_tab(self, name: str) -> None:
        """点击指定分类标签，等待内容刷新。"""
        tab = self.s4_category_tabs().filter(has_text=name)
        tab.click()
        self.page.wait_for_timeout(500)

    # ── 第五屏 ─────────────────────────────────────────────
    def screen5(self) -> Locator:
        return self.get_locator("screen5")

    def s5_contact_btn(self) -> Locator:
        return self.get_locator("s5_contact_btn")

    def s5_trial_link(self) -> Locator:
        return self.get_locator("s5_trial_link")

    def s5_ai_cases(self) -> Locator:
        return self.get_locator("s5_ai_case")

    def get_s5_slider_value(self, index: int = 0) -> str:
        """获取第 index 个对比滑块的当前 value。"""
        return self.page.locator(".ylAiSliderInput").nth(index).get_attribute("value") or ""

    def click_contact_btn_and_get_popup(self) -> Optional[Locator]:
        """点击联系商务，返回弹出的二维码弹窗 locator（若存在）。"""
        self.s5_contact_btn().click()
        self.page.wait_for_timeout(800)
        # 尝试通用 modal/dialog 定位
        popup = self.page.locator("[class*='modal'],[class*='Modal'],[class*='dialog'],[class*='qr'],[role='dialog']")
        return popup if popup.count() > 0 else None

    # ── 第六屏 ─────────────────────────────────────────────
    def screen6(self) -> Locator:
        return self.get_locator("screen6")

    def s6_dynamic_subtitle(self) -> Locator:
        return self.get_locator("s6_dynamic_subtitle")

    def s6_stat_grid(self) -> Locator:
        return self.get_locator("s6_stat_grid")

    def s6_review_cards(self) -> Locator:
        return self.get_locator("s6_review_card")

    def s6_review_track(self) -> Locator:
        return self.get_locator("s6_review_track")

    def s6_prev_btn(self) -> Locator:
        return self.get_locator("s6_prev_btn")

    def s6_next_btn(self) -> Locator:
        return self.get_locator("s6_next_btn")

    def get_dynamic_numbers(self) -> Tuple[Optional[int], Optional[int]]:
        """从第六屏动态文案中提取两个数字（设计师数、效果图数）。"""
        txt = self.s6_dynamic_subtitle().inner_text()
        nums = re.findall(r'\d+', txt)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        return None, None

    def get_review_track_transform(self) -> str:
        """获取评论轨道的 transform 属性值（用于判断滚动方向）。"""
        return self.s6_review_track().evaluate(
            "(el) => getComputedStyle(el).transform"
        ) or ""

    def get_visible_review_count(self) -> int:
        """获取当前视口内可见的评论卡片数量。"""
        count = self.s6_review_cards().count()
        visible = 0
        for i in range(count):
            if self.is_in_viewport(self.s6_review_cards().nth(i)):
                visible += 1
        return visible

    # ── 第七屏 ─────────────────────────────────────────────
    def screen7(self) -> Locator:
        return self.get_locator("screen7")

    def screen7_heading(self) -> Locator:
        return self.get_locator("screen7_heading")

    def s7_dl_client_btn(self) -> Locator:
        return self.get_locator("s7_dl_client_btn")

    def s7_dl_ai_btn(self) -> Locator:
        return self.get_locator("s7_dl_ai_btn")

    def s7_trust_tags(self) -> Locator:
        return self.get_locator("s7_trust_tags")

    def s7_trust_tag_list(self) -> Locator:
        return self.get_locator("s7_trust_tag")

    def get_trust_tag_texts(self) -> List[str]:
        """返回第七屏信任标签文本列表。"""
        count = self.s7_trust_tag_list().count()
        return [self.s7_trust_tag_list().nth(i).inner_text().strip() for i in range(count)]

    def get_screen7_text(self) -> str:
        """返回第七屏区域全部文本。"""
        return self.screen7().inner_text()

    # ── 全局工具 ─────────────────────────────────────────────
    def get_page_text(self) -> str:
        """获取整页文本（用于文案全局检索）。"""
        return self.page.locator("body").inner_text()

    def count_text_occurrences(self, text: str) -> int:
        """统计页面中特定文本出现次数（用于文案检查）。"""
        return self.page.get_by_text(text, exact=True).count()

    def click_and_capture_navigation(self, locator: Locator) -> Optional[str]:
        """点击元素并捕获新页面/导航 URL（处理 target=_blank 和同页跳转）。"""
        try:
            with self.page.context.expect_page(timeout=5000) as new_page_info:
                locator.click()
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")
            return new_page.url
        except Exception:
            # 同页锚点跳转
            self.page.wait_for_timeout(800)
            return None

    def get_current_url(self) -> str:
        return self.page.url

    # ── 埋点辅助方法 ────────────────────────────────────────────

    def click_hero_download_version(self, keyword: str = "Win10") -> None:
        """触发首屏下载埋点：点 CTA → 等 Popover 出现 → 点版本项。

        GIO 事件 render_download_click 在 Popover 版本项点击时上报，
        直接点 CTA 不触发，必须经由此两步流程。

        Args:
            keyword: 版本关键词，默认 "Win10"（对应 data2 = "首屏CTA-Win10"）。
        """
        # 第一步：点首屏 CTA，触发 Ant Popover 弹出
        self.screen1_cta_btn().click(timeout=5000, no_wait_after=True)
        self.page.wait_for_timeout(800)
        # 第二步：点 Popover 内版本选择项
        item = self.get_locator("download_version_popover_item").filter(
            has_text=keyword
        )
        item.first.click(timeout=3000, no_wait_after=True)
        self.page.wait_for_timeout(1200)

    def scroll_through_all_screens(self) -> None:
        """依次滚过全部 7 屏，触发各屏 render_screen_show 曝光事件。

        每屏等待 700ms 确保 GIO 埋点上报完成后再继续。
        """
        screens = [
            "#yl-hero",
            "#yl-why",
            "#yl-workflow",
            "#yl-cases",
            "#yl-ai",
            "#yl-reviews",
            "#yl-download",
        ]
        for sid in screens:
            try:
                self.scroll_to_screen(sid)
            except PlaywrightError as exc:
                # 某屏锚点 evaluate 失败（极少发生，JS 已有 null 守卫）时跳过，不中断流程
                _logger.debug("scroll_through_all_screens: skip %s — %s", sid, exc)
            self.page.wait_for_timeout(700)
