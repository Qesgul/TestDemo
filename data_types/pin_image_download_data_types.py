from dataclasses import dataclass


@dataclass
class PinDownloadConfig:
    """图钉新品页图片下载测试参数配置。"""
    repeat_count: int = 100          # 目标下载触发次数（每次使用不同图片）
    max_scroll_attempts: int = 30    # 找不到新图片时最多滚动次数（安全阀）
    scroll_pixels: int = 800         # 每次滚动像素数
