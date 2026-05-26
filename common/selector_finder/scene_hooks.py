"""
场景钩子：在 AI 快照前对页面做预处理，解决特定场景的定位难题。

内置钩子：
  - popup_clear：清除 ant-design 遮罩弹窗
  - wait_network_idle：等待动态内容加载完毕
  - upload_detect：探测 input[type=file]，标记上传场景

新增场景：在 SCENE_HOOKS 字典添加一项即可，主流程不变。
"""

from __future__ import annotations

import logging
from typing import Callable

from playwright.sync_api import Page

from common.selector_finder.models import ExtractedStep

_logger = logging.getLogger(__name__)

# 关键词 → 触发 upload_detect 钩子
_UPLOAD_KEYWORDS = ("上传", "截图", "图片", "文件", "upload", "attach")


# ── 内置钩子实现 ─────────────────────────────────────────────────────────────

def _hook_popup_clear(page: Page, step: ExtractedStep) -> None:
    """移除 ant-design 模态遮罩和 body 滚动锁定（与 BasePage.goto() 同款处理）。"""
    try:
        page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.body.classList.remove('ant-scrolling-effect');
            document.body.style.overflow = '';
        }""")
    except Exception as e:
        _logger.debug("popup_clear 钩子异常: %s", e)


def _hook_wait_network_idle(page: Page, step: ExtractedStep) -> None:
    """等待网络空闲，适用于 SPA 动态加载场景。

    仅在 step 描述含"加载"/"动态"/"滚动"/"无限"时触发，
    避免对普通页面增加不必要的等待时间。
    """
    trigger_words = ("加载", "动态", "滚动", "无限", "lazy", "scroll", "infinite")
    if any(kw in step.description for kw in trigger_words):
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception as e:
            _logger.debug("wait_network_idle 钩子超时（可接受）: %s", e)


def _hook_upload_detect(page: Page, step: ExtractedStep) -> None:
    """
    探测页面中的 input[type=file] 元素。

    如果步骤描述含上传关键词，则把 step.action 置为 'upload'，
    并在 step 上附加 _file_input_css 属性（供 ai_resolver 优先使用）。
    """
    desc = (step.element_desc or "") + (step.description or "")
    if not (step.action == "upload" or any(kw in desc for kw in _UPLOAD_KEYWORDS)):
        return

    try:
        file_input_css = page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            if (!inputs.length) return null;
            // 返回第一个可见（或隐藏但可 set_input_files 调用）的 input 的 CSS selector
            const el = inputs[0];
            // 尝试构造稳定 selector：id > name > 层级路径
            if (el.id) return '#' + el.id;
            if (el.name) return 'input[name="' + el.name + '"]';
            return 'input[type="file"]';
        }""")
        if file_input_css:
            step.action = "upload"
            # 附加到 step（非标准字段，ai_resolver 读取后转 LocatorSpec）
            step.__dict__["_file_input_css"] = file_input_css
            _logger.info("upload_detect：发现 file input %r，step.action 置 upload", file_input_css)
    except Exception as e:
        _logger.debug("upload_detect 钩子异常: %s", e)


# ── 钩子注册表 ───────────────────────────────────────────────────────────────
# key: 场景名称（仅用于日志）
# value: Callable[[Page, ExtractedStep], None]
#
# 要新增场景，只需在此添加一项——主流程不需要改动。

SCENE_HOOKS: dict[str, Callable[[Page, ExtractedStep], None]] = {
    "popup_clear": _hook_popup_clear,
    "wait_network_idle": _hook_wait_network_idle,
    "upload_detect": _hook_upload_detect,
}


def apply_hooks(page: Page, step: ExtractedStep) -> None:
    """依序执行所有场景钩子，单个失败不中断后续钩子。"""
    for name, hook in SCENE_HOOKS.items():
        try:
            hook(page, step)
        except Exception as e:
            _logger.warning("场景钩子 %s 异常（已忽略）: %s", name, e)
