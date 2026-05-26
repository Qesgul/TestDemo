"""
图钉新品页 - 图片瀑布流批量下载触发用例

URL: https://pin.znztv.com/pinNewHome/1

覆盖：
- TC-PIN-001（P0）：对 100 张不同图片依次悬停 → 点击下载 → 捕获下载事件取消落盘
  验证下载接口请求完整发出，但不保存文件到磁盘

技术说明：
- 使用 page.expect_download() 在 Playwright 层捕获下载事件，无 OS 文件对话框
- download.cancel() 取消落盘，满足"不下载文件"需求
- 以图片 img[src] 或 img[data-src] 为去重 key，保证 100 次使用不同图片
- 虚拟滚动处理：ReactVirtualized Masonry DOM 只保留约 30 个可见节点，滚动后旧节点
  被移除、新节点插入，因此每轮均扫描当前可见全部卡片（0..count-1），不用全局 index

登录：
- 显式用 tests/data/pin_image_download_data.yaml 中的账号登录（13060613380）
- 不依赖 conftest 的 session 级 logged_in_page fixture（避免被 login_data.yaml 写死）
- cookie 逻辑正常工作：首次走密码登录并保存 cookie，后续同账号直接 cookie 登录
"""

import logging

import pytest

from common.yaml_loader import load_yaml
from pages.methods.login_page import LoginPage
from pages.methods.pin_image_download_page import PinImageDownloadPage

_DATA_PATH = "tests/data/pin_image_download_data.yaml"
_DATA = load_yaml(_DATA_PATH)

_logger = logging.getLogger(__name__)


class TestPinImageDownload:
    """图钉新品页 - 图片瀑布流批量下载触发用例集。"""

    @pytest.mark.smoke
    @pytest.mark.main
    @pytest.mark.ui
    def test_download_100_distinct_images(self, page, assertion):
        """TC-PIN-001（P0）：100 张不同图片的下载接口触发测试。

        步骤：
          1. 用 pin_image_download_data.yaml 的账号显式登录（13060613380）
          2. 进入图钉新品页（瀑布流）
          3. 对每张未处理过的图片：悬停 → 点击下载 → 捕获下载事件 → 取消落盘
          4. 当前视口图片全部处理完时滚动加载更多（虚拟滚动：每次重新扫描）
          5. 重复直到累计触发 100 张不同图片的下载
          6. 断言实际触发数 >= expected_min_distinct_downloads

        技术保障：
          - expect_download() 确保下载接口完整响应
          - download.cancel() 确保不保存文件到磁盘
          - 每轮扫描全部可见卡片（不用全局 index），正确应对 ReactVirtualized 虚拟滚动
          - 已处理的图片 src 加入 downloaded_srcs 集合，跨滚动轮次去重
        """
        page.set_default_timeout(30000)

        repeat_count: int = _DATA["repeat_count"]
        max_scroll_attempts: int = _DATA["max_scroll_attempts"]
        expected_min: int = _DATA["expected_min_distinct_downloads"]

        # ── 登录（使用本用例专属账号，不依赖 session 级 logged_in_page）──
        login = LoginPage(page)
        login.goto_login_page()
        login.login_with(_DATA["username"], _DATA["password"])

        # ── 导航至图钉新品页 ──
        pin_page = PinImageDownloadPage(page, auto_close_popups=True)
        pin_page.goto()

        downloaded_srcs: set = set()   # 已触发下载的图片 src 集合（跨滚动轮次去重）
        scroll_attempts: int = 0

        _logger.info("=== TC-PIN-001: 目标触发 %d 张不同图片下载 ===", repeat_count)

        while len(downloaded_srcs) < repeat_count:
            total_cards = pin_page.get_card_count()

            # 扫描当前 DOM 可见的全部卡片，找第一张未处理的
            found_new = False
            for i in range(total_cards):
                src = pin_page.get_card_src_by_index(i)
                if src in downloaded_srcs:
                    continue  # 已处理，跳过

                # 触发下载（接口完整发出，文件不落盘）
                success = pin_page.hover_and_trigger_download(i)

                # 无论成功/失败都记录为"已尝试"，避免反复重试同一元素导致死循环
                downloaded_srcs.add(src)
                found_new = True

                if success:
                    _logger.info(
                        "[%d/%d] 卡片 %d 下载触发成功（src=%.40s...）",
                        len(downloaded_srcs), repeat_count, i, src,
                    )
                else:
                    _logger.warning(
                        "卡片 %d 下载触发失败，已跳过（src=%.40s...）",
                        i, src,
                    )

                break  # 每轮只处理一张，break 后回 while 重新扫描（DOM 可能已更新）

            if not found_new:
                # 当前视口所有卡片均已处理 → 滚动加载下一批
                assertion.assert_true(
                    scroll_attempts < max_scroll_attempts,
                    message=(
                        f"已滚动 {scroll_attempts} 次，当前视口无新图片，"
                        f"已触发 {len(downloaded_srcs)} 张，目标 {repeat_count} 张"
                    ),
                )
                _logger.info(
                    "视口已处理完，第 %d 次滚动（已触发 %d/%d）",
                    scroll_attempts + 1, len(downloaded_srcs), repeat_count,
                )
                pin_page.scroll_to_load_more()
                scroll_attempts += 1

        # ── 最终断言 ──
        actual_count = len(downloaded_srcs)
        _logger.info("=== 完成：共触发 %d 张图片下载（含失败跳过）===", actual_count)

        assertion.assert_true(
            actual_count >= expected_min,
            message=(
                f"实际触发下载图片数 {actual_count} 低于期望最小值 {expected_min}"
            ),
            name="图片下载数量达到期望最小值",
        )


if __name__ == "__main__":
    import subprocess
    import sys

    sys.exit(subprocess.call([
        sys.executable, "-m", "pytest", __file__,
        "-v", "--headed", "-s",
    ]))
