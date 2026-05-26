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
"""
import logging
from typing import Optional, Set

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage, PopupStrategy

_logger = logging.getLogger(__name__)

# YAML 键名常量（与 pin_image_download_elements.yaml 一一对应）
_KEY_CARD_LIST = "step1_瀑布流图片卡片列表"
_KEY_CARD = "step2_单张图片卡片"
_KEY_DOWNLOAD_BTN = "step3_图片卡片下载按钮"


class PinImageDownloadPage(BasePage):
    """图钉新品页 - 图片瀑布流下载操作类。"""

    DEFAULT_URL = "https://pin.znztv.com/pinNewHome/1"

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

    def get_visible_card_srcs(self) -> Set[str]:
        """返回当前视口内所有可见图片卡片的唯一标识（img src）。

        使用 img[src] 作为去重 key，避免同一图片被重复下载。
        如果 src 为空（懒加载），改用 DOM 索引作为 fallback key。
        """
        # TODO[locate]: 依赖 step1_瀑布流图片卡片列表 selector 就绪后实现
        try:
            cards = self.get_locator(_KEY_CARD_LIST)
            count = cards.count()
            srcs: Set[str] = set()
            for i in range(count):
                card = cards.nth(i)
                try:
                    img = card.locator("img").first
                    src = img.get_attribute("src") or ""
                    # 懒加载时 src 为 data-src
                    if not src or src.startswith("data:"):
                        src = img.get_attribute("data-src") or f"__idx_{i}"
                    srcs.add(src)
                except Exception:
                    srcs.add(f"__idx_{i}")
            return srcs
        except Exception as e:
            _logger.warning("get_visible_card_srcs 失败: %s", e)
            return set()

    def get_card_count(self) -> int:
        """返回当前页面可见的图片卡片数量。"""
        try:
            return self.get_locator(_KEY_CARD_LIST).count()
        except Exception:
            return 0

    def hover_and_trigger_download(self, card_index: int) -> bool:
        """悬停第 N 张卡片并触发下载，使用 expect_download 捕获下载事件。

        下载接口请求会完整发出（HTTP 响应头到达），但文件不落盘。

        Args:
            card_index: 卡片的 0-based 序号

        Returns:
            True 表示成功触发下载事件并取消落盘；False 表示操作失败。
        """
        try:
            cards = self.get_locator(_KEY_CARD_LIST)
            card = cards.nth(card_index)

            # 悬停触发下载按钮出现
            card.hover(timeout=5000)
            self.page.wait_for_timeout(300)  # 等待 hover 动效

            # 等待下载事件捕获（不落盘）
            with self.page.expect_download(timeout=15000) as dl_info:
                download_btn = card.locator(
                    self._get_raw_selector(_KEY_DOWNLOAD_BTN)
                ).first
                download_btn.click(timeout=5000)

            download = dl_info.value
            # 取消落盘：接口请求已完成，文件不保存到磁盘
            download.cancel()

            _logger.info("卡片 [%d] 下载事件触发并取消落盘成功", card_index)
            return True

        except PlaywrightTimeoutError as e:
            _logger.warning("卡片 [%d] 等待下载超时: %s", card_index, e)
            # ESC 兜底：关闭可能出现的浏览器内下载确认条
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False
        except Exception as e:
            _logger.warning("卡片 [%d] 下载触发失败: %s", card_index, e)
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False

    def _get_raw_selector(self, key: str) -> str:
        """从 YAML 获取原始 CSS selector 字符串，用于 locator().locator() 链式定位。"""
        spec = self._elements.get(key, {})
        if isinstance(spec, str):
            return spec
        return spec.get("selector", spec.get("css", ""))

    def scroll_to_load_more(self, scroll_pixels: int = 800) -> None:
        """向下滚动以触发瀑布流加载下一批图片。"""
        self.page.mouse.wheel(0, scroll_pixels)
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeoutError:
            # networkidle 可能不会触发，继续执行
            self.page.wait_for_timeout(800)
        _logger.debug("滚动 %d px，等待新图片加载", scroll_pixels)

    def get_card_src_by_index(self, index: int) -> str:
        """获取指定卡片的唯一标识 src（用于去重记录）。"""
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
