"""
图钉新品页 - 图片瀑布流下载 Page Object。

覆盖范围：
- 瀑布流图片枚举（通过 src 属性或 DOM key 去重）
- 悬停触发下载按钮
- 使用 page.expect_download() 捕获下载事件（接口请求完整发出）
  但不落盘（调用 download.cancel()），避免保存文件到磁盘
- 自动滚动加载更多图片

URL: https://pin.znztv.com/pinNewHome/1

元素 YAML：pages/elements/pin_image_download_elements.yaml
  - 所有 selector 由 ai-selector skill 生成 + verify_locator.py 验证

性能说明：
  - get_all_card_srcs()：单次 evaluate() 批量取全部卡片 src，替代逐张 RPC
  - hover_and_trigger_download() 前置预检：懒加载卡片（src 为空）跳过 hover，
    节省每张约 0.5s（scrollIntoView + hover + 300ms 等待）
"""
import logging
from typing import List, Optional, Set

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage, PopupStrategy

_logger = logging.getLogger(__name__)

# YAML 键名常量（与 pin_image_download_elements.yaml 一一对应）
_KEY_CARD_LIST = "step1_瀑布流图片卡片列表"
_KEY_CARD = "step2_单张图片卡片"
_KEY_DOWNLOAD_BTN = "step3_图片卡片下载按钮"


class PinImageDownloadPage(BasePage):
    """图钉新品页 - 图片瀑布流下载操作类。"""

    DEFAULT_URL = "https://interior.znzmo.com/pinNewHome/1-20"

    def __init__(self, page: Page, auto_close_popups: bool = True) -> None:
        super().__init__(
            page=page,
            elements_yaml_path="pages/elements/pin_image_download_elements.yaml",
            auto_close_popups=auto_close_popups,
        )

    def goto(self, url: Optional[str] = None, **kwargs) -> None:
        """导航至图钉新品页（唯一 URL 配置点）。"""
        super().goto(url or self.DEFAULT_URL, **kwargs)
        # 等待瀑布流首批图片加载
        self.page.wait_for_load_state("networkidle", timeout=15000)

    # ──────────────────────────────────────────────────────────
    # 批量 / 计数工具
    # ──────────────────────────────────────────────────────────

    def get_card_count(self) -> int:
        """返回当前页面可见的图片卡片数量。"""
        try:
            return self.get_locator(_KEY_CARD_LIST).count()
        except Exception:
            return 0

    def get_all_card_srcs(self) -> List[str]:
        """单次 evaluate() 批量返回全部可见卡片的 src 列表。

        性能优化核心：替代逐张调用 get_card_src_by_index()。
        N 张卡片只发 1 次 RPC（原方案每张 1-2 次，扫描 30 张需 30-60 次）。

        懒加载/未渲染的卡片返回 '__idx_<N>' 占位，与 get_card_src_by_index 保持一致。
        """
        try:
            return self.page.evaluate("""() => {
                const cards = document.querySelectorAll('#masonry li');
                return Array.from(cards).map(function(card, idx) {
                    var img = card.querySelector('img');
                    if (!img) return '__idx_' + idx;
                    var src = (img.getAttribute('src') || '').trim();
                    if (src && !src.startsWith('data:')) return src;
                    var dataSrc = (img.getAttribute('data-src') || '').trim();
                    return dataSrc || ('__idx_' + idx);
                });
            }""")
        except Exception as e:
            _logger.warning("get_all_card_srcs 失败，回退逐张: %s", e)
            count = self.get_card_count()
            return [self.get_card_src_by_index(i) for i in range(count)]

    def get_card_src_by_index(self, index: int) -> str:
        """获取指定卡片的唯一标识 src（用于去重记录）。

        注：批量扫描场景请优先用 get_all_card_srcs()，性能更优。
        """
        try:
            cards = self.get_locator(_KEY_CARD_LIST)
            card = cards.nth(index)
            img = card.locator("img").first
            src = img.get_attribute("src") or ""
            if not src or src.startswith("data:"):
                src = img.get_attribute("data-src") or f"__idx_{index}"
            return src
        except Exception:
            return f"__idx_{index}"

    def get_visible_card_srcs(self) -> Set[str]:
        """返回当前视口内所有可见图片卡片的唯一标识集合。"""
        return set(self.get_all_card_srcs())

    # ──────────────────────────────────────────────────────────
    # 核心下载操作
    # ──────────────────────────────────────────────────────────

    def hover_and_trigger_download(self, card_index: int) -> bool:
        """悬停第 N 张卡片并触发下载，使用 expect_download 捕获下载事件。

        下载接口请求会完整发出（HTTP 响应头到达），但文件不落盘。

        性能优化（与之前版本的关键差异）：
        - 前置预检（evaluate）：在 hover 之前用一次 JS 判断图片是否已加载。
          懒加载卡片（img.src 为空）直接返回 False，无需走 scrollIntoView +
          hover + 300ms 等待 + count() 检查，每张节省约 0.5s。
        - 下载 timeout 8s（原 15s）：blob 通常 1-4s 就绪，8s 已足够兜底。

        已知问题及处理：
        1. 固定 Header（z-index=1000）拦截点击：scrollIntoView 居中 + force=True。
        2. 成功路径也必须调 _cleanup_hover()：否则 hover 覆盖层残留，下一轮
           ReactVirtualized 虚拟滚动重绘时页面视觉"卡住"。

        Args:
            card_index: 卡片的 0-based 序号

        Returns:
            True 表示成功触发下载事件并取消落盘；False 表示操作失败或跳过。
        """
        try:
            cards = self.get_locator(_KEY_CARD_LIST)
            card = cards.nth(card_index)

            # ── 前置预检：图片未加载则直接跳过（不 hover，节省 ~0.5s/张）──
            try:
                img_loaded = card.evaluate("""el => {
                    var img = el.querySelector('img');
                    if (!img) return false;
                    var src = (img.getAttribute('src') || '').trim();
                    return !!(src && !src.startsWith('data:'));
                }""")
            except Exception:
                img_loaded = True  # 预检失败时保守处理，继续 hover

            if not img_loaded:
                _logger.debug("卡片 [%d] 图片未加载，跳过 hover", card_index)
                return False

            # ── 正式 hover 流程 ──

            # 将卡片滚动到视口中央，避免固定 Header 遮挡下载按钮
            try:
                card.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
                self.page.wait_for_timeout(200)
            except Exception:
                pass

            card.hover(timeout=5000)
            self.page.wait_for_timeout(300)

            # 再次检查：hover 后下载按钮是否出现（防止图片加载检查通过但按钮未渲染）
            dl_raw = self._get_raw_selector(_KEY_DOWNLOAD_BTN)
            dl_locator = card.locator(dl_raw)
            if dl_locator.count() == 0:
                _logger.debug("卡片 [%d] hover 后下载按钮未出现，跳过", card_index)
                self._cleanup_hover()
                return False

            download_btn = dl_locator.first

            # 捕获下载事件（不落盘）
            # force=True：绕过固定 Header 拦截（已 scrollIntoView 确保可见）
            with self.page.expect_download(timeout=8000) as dl_info:
                download_btn.click(timeout=5000, force=True)

            download = dl_info.value
            download.cancel()

            _logger.info("卡片 [%d] 下载事件触发并取消落盘成功", card_index)
            self._cleanup_hover()
            return True

        except PlaywrightTimeoutError as e:
            _logger.warning("卡片 [%d] 等待下载超时: %s", card_index, e)
            self._cleanup_hover()
            return False
        except Exception as e:
            _logger.warning("卡片 [%d] 下载触发失败: %s", card_index, e)
            self._cleanup_hover()
            return False

    def _cleanup_hover(self) -> None:
        """每次 hover_and_trigger_download 结束后统一清理页面 hover 状态。

        移开鼠标 + 按 Escape 消除工具提示/浮层 + 等 200ms 让页面稳定。
        保证 ReactVirtualized 虚拟滚动重绘时不会有残留覆盖层。
        """
        try:
            self.page.mouse.move(10, 10)
        except Exception:
            pass
        try:
            self.page.keyboard.press("Escape")
        except Exception:
        	pass
        try:
            self.page.wait_for_timeout(200)
        except Exception:
            pass

    def _get_raw_selector(self, key: str) -> str:
        """从 YAML 获取原始 CSS selector 字符串，用于 locator().locator() 链式定位。"""
        spec = self._elements.get(key, {})
        if isinstance(spec, str):
            return spec
        return spec.get("selector", spec.get("css", ""))

    # ──────────────────────────────────────────────────────────
    # 滚动加载
    # ──────────────────────────────────────────────────────────

    def scroll_to_load_more(self, scroll_pixels: int = 800) -> None:
        """向下滚动以触发瀑布流加载下一批图片。

        ReactVirtualized 虚拟滚动：滚动后旧 DOM 被移除、新 DOM 插入，
        需等待 networkidle 或固定延迟，确保新卡片图片加载完成后再扫描。
        """
        self.page.mouse.wheel(0, scroll_pixels)
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeoutError:
            # networkidle 可能不会触发（SPA + 虚拟滚动），用固定延迟兜底
            self.page.wait_for_timeout(1500)
        _logger.debug("滚动 %d px，等待新图片加载", scroll_pixels)
