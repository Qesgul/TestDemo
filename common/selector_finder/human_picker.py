"""
人工兜底：启动有头浏览器，注入 inspector.js，收集用户点选结果。

每个 missing 元素在浮窗顶栏逐一提示，用户点击对应元素后自动进入下一个。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import sync_playwright

from common.selector_finder.models import ExtractedStep, LocatorSpec, ResolvedElement

_logger = logging.getLogger(__name__)

_INSPECTOR_JS = Path(__file__).parent / "inspector.js"


_UPLOAD_KEYWORDS = ("上传", "截图", "图片", "文件", "upload")


def _spec_from_dict(d: dict[str, Any]) -> Optional[LocatorSpec]:
    """把 inspector.js chosenSpec dict 转 LocatorSpec。"""
    if not d or not d.get("strategy"):
        return None
    s = d["strategy"]
    if s == "test_id":
        return LocatorSpec(strategy="test_id", test_id=d.get("test_id"))
    if s == "role":
        return LocatorSpec(
            strategy="role",
            role=d.get("role"),
            name=d.get("name"),
            exact=bool(d.get("exact", False)),
        )
    if s == "label":
        return LocatorSpec(strategy="label", label=d.get("label"), exact=bool(d.get("exact", False)))
    if s == "placeholder":
        return LocatorSpec(strategy="placeholder", placeholder=d.get("placeholder"))
    if s == "text":
        return LocatorSpec(strategy="text", text=d.get("text"), exact=bool(d.get("exact", True)))
    if s == "css":
        return LocatorSpec(strategy="css", selector=d.get("selector"))
    return None


def _maybe_force_upload(step: ExtractedStep, info: dict[str, Any]) -> Optional[LocatorSpec]:
    """上传场景强制走 <input type="file"> + action=upload。"""
    file_css = info.get("fileInputCss")
    if not file_css:
        return None
    desc = step.element_desc or ""
    if step.action == "upload" or any(kw in desc for kw in _UPLOAD_KEYWORDS):
        step.action = "upload"
        return LocatorSpec(strategy="css", selector=file_css)
    return None


def _raw_to_locator_spec(info: dict[str, Any]) -> Optional[LocatorSpec]:
    """优先使用用户在浏览器端选定的策略，否则按默认优先级回退。"""
    chosen = _spec_from_dict(info.get("chosenSpec") or {})
    if chosen:
        return chosen
    # 回退：保持旧版优先级，防止 chosenSpec 缺失时 crash
    if info.get("testId"):
        return LocatorSpec(strategy="test_id", test_id=info["testId"])
    if info.get("role") and info.get("name"):
        return LocatorSpec(strategy="role", role=info["role"], name=info["name"], exact=False)
    if info.get("label"):
        return LocatorSpec(strategy="label", label=info["label"])
    if info.get("placeholder"):
        return LocatorSpec(strategy="placeholder", placeholder=info["placeholder"])
    if info.get("text"):
        return LocatorSpec(strategy="text", text=info["text"], exact=True)
    if info.get("css"):
        return LocatorSpec(strategy="css", selector=info["css"])
    return None


def _build_alternatives(info: dict[str, Any], primary: LocatorSpec) -> list[LocatorSpec]:
    """从 info 中提取除主策略外的备选 LocatorSpec。"""
    candidates: list[LocatorSpec] = []

    if info.get("testId"):
        candidates.append(LocatorSpec(strategy="test_id", test_id=info["testId"]))
    if info.get("role") and info.get("name"):
        candidates.append(LocatorSpec(strategy="role", role=info["role"], name=info["name"]))
    if info.get("label"):
        candidates.append(LocatorSpec(strategy="label", label=info["label"]))
    if info.get("placeholder"):
        candidates.append(LocatorSpec(strategy="placeholder", placeholder=info["placeholder"]))
    if info.get("text"):
        candidates.append(LocatorSpec(strategy="text", text=info["text"], exact=True))
    if info.get("css"):
        candidates.append(LocatorSpec(strategy="css", selector=info["css"]))

    def _same(a: LocatorSpec, b: LocatorSpec) -> bool:
        if a.strategy != b.strategy:
            return False
        if a.strategy == "css":
            return a.selector == b.selector
        if a.strategy == "text":
            return a.text == b.text
        if a.strategy == "role":
            return a.role == b.role and a.name == b.name
        if a.strategy == "label":
            return a.label == b.label
        if a.strategy == "placeholder":
            return a.placeholder == b.placeholder
        if a.strategy == "test_id":
            return a.test_id == b.test_id
        return False

    return [c for c in candidates if not _same(c, primary)]


def pick_missing(
    url: str,
    missing_steps: list[ExtractedStep],
    browser_type: str = "chromium",
    storage_state: Optional[str] = None,
) -> list[ResolvedElement]:
    """
    启动有头浏览器，让用户逐一点选 AI 未能解析的元素。

    返回：ResolvedElement 列表（source="human"），跳过的项不包含在内。
    """
    if not missing_steps:
        return []

    import json as _json
    import time as _time

    descriptions = [step.element_desc for step in missing_steps]
    picks: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = getattr(pw, browser_type).launch(headless=False)
        ctx_kwargs: dict = {}
        if storage_state:
            ctx_kwargs["storage_state"] = storage_state
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        # 注入 inspector.js（每次导航前执行，定义 window.__selectorFinder）
        page.add_init_script(path=str(_INSPECTOR_JS))

        # 将 descriptions 注入为全局变量，按钮 onclick 直接调用 createPicker
        page.add_init_script(script=f"window.__sfDescriptions = {_json.dumps(descriptions)};")

        # 顶部横条：每次导航/刷新后自动出现，不阻挡页面内容
        page.add_init_script(script="""
            (function () {
                function showBar() {
                    if (document.getElementById('__sf-ready-bar')) return;
                    var bar = document.createElement('div');
                    bar.id = '__sf-ready-bar';
                    bar.style.cssText = [
                        'position:fixed','top:0','left:0','right:0',
                        'background:#1e1b4b','color:#fff',
                        'z-index:2147483647','padding:10px 20px',
                        'display:flex','align-items:center','gap:16px',
                        'font-size:14px','font-family:sans-serif',
                        'box-shadow:0 2px 8px rgba(0,0,0,0.4)'
                    ].join(';');
                    var tip = document.createElement('span');
                    tip.textContent = '[Selector Finder] 登录并关闭弹窗后，点击右侧按钮开始选取元素';
                    tip.style.flex = '1';
                    var btn = document.createElement('button');
                    btn.textContent = '开始选取元素';
                    btn.style.cssText = [
                        'background:#4f46e5','color:#fff','border:none',
                        'padding:8px 20px','border-radius:6px',
                        'font-size:14px','cursor:pointer','white-space:nowrap'
                    ].join(';');
                    btn.onclick = function() {
                        bar.remove();
                        if (window.__selectorFinder && window.__sfDescriptions) {
                            window.__selectorFinder.createPicker(window.__sfDescriptions);
                        }
                    };
                    bar.appendChild(tip);
                    bar.appendChild(btn);
                    document.body.appendChild(bar);
                }
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', showBar);
                } else {
                    showBar();
                }
            })();
        """)

        # 导航到目标页面
        page.goto(url, wait_until="domcontentloaded")

        _logger.info("等待用户登录并点击'开始选取元素'按钮...")

        # 轮询 window.__sfDone / window.__sfPicks，浏览器关闭时 evaluate 抛异常退出
        deadline = _time.monotonic() + 600
        while _time.monotonic() < deadline:
            try:
                state = page.evaluate("""() => ({
                    done: !!window.__sfDone,
                    count: (window.__sfPicks || []).length
                })""")
                if state["done"] or state["count"] >= len(descriptions):
                    _logger.info("点选完成，共 %d 条，正在收集结果...", state["count"])
                    picks = page.evaluate("() => window.__sfPicks || []")
                    break
            except Exception:
                _logger.info("浏览器已关闭，使用已收集结果")
                break
            _time.sleep(0.5)

        _logger.info("关闭浏览器...")
        try:
            browser.close()
        except Exception:
            pass

    # 将 picks 映射回 ResolvedElement
    result: list[ResolvedElement] = []
    for i, info in enumerate(picks):
        if i >= len(missing_steps):
            break
        step = missing_steps[i]

        # 1) 上传场景强制 input[type=file]
        forced = _maybe_force_upload(step, info)
        spec = forced or _raw_to_locator_spec(info)
        if spec is None:
            _logger.warning("无法从点选结果构建 locator: %s", info)
            continue

        alternatives = _build_alternatives(info, spec)
        result.append(
            ResolvedElement(
                element_desc=step.element_desc,
                step_index=step.step_index,
                action=step.action,
                value=step.value,
                locator=spec,
                alternatives=alternatives,
                verified=False,
                source="human",
                attempts=0,
            )
        )
        _logger.info(
            "人工点选 #%d %r → strategy=%s action=%s",
            step.step_index, step.element_desc, spec.strategy, step.action,
        )

    return result
