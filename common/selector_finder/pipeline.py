"""
完整运行流水线：提取步骤 → [yaml 复用] → [人工兜底] → 输出 YAML。

两阶段优先级：
  1. yaml_reuse：在现有 pages/elements/*.yaml 中找匹配 key，verifier 确认仍可用
  2. human_picker：有头浏览器人工点选（兜底）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from common.selector_finder import extractor, human_picker, scene_hooks, yaml_reuse
from common.selector_finder.models import ExtractedStep, ResolvedElement, SelectorReport
from common.selector_finder.verifier import is_unique

_logger = logging.getLogger(__name__)


# ── 输出工具函数 ─────────────────────────────────────────────────────────────

def _to_elements_yaml(resolved: list[ResolvedElement]) -> dict:
    """将解析结果转为 BasePage.get_locator() 兼容的 YAML 字典。"""
    elements: dict = {}
    for item in resolved:
        if item.locator is None:
            continue
        key = f"step{item.step_index}_{item.element_desc}"
        entry = item.locator.to_yaml_dict()
        if item.action == "upload":
            entry["action"] = "upload"
        elements[key] = entry
    return elements


def _to_report_yaml(report: SelectorReport, resolved: list[ResolvedElement]) -> dict:
    """生成完整报告 YAML（含元数据和备选策略）。"""
    steps_data = []
    for item in resolved:
        step: dict = {
            "step_index": item.step_index,
            "description": item.element_desc,
            "action": item.action,
            "source": item.source,
            "verified": item.verified,
        }
        if item.value:
            step["value"] = item.value
        if item.locator:
            step["locator"] = item.locator.to_yaml_dict()
        if item.alternatives:
            step["alternatives"] = [a.to_yaml_dict() for a in item.alternatives]
        steps_data.append(step)

    missing_data = [
        {"step_index": s.step_index, "description": s.element_desc, "action": s.action}
        for s in report.missing
    ]

    return {
        "meta": {
            "test_case_file": report.test_case_file,
            "target_url": report.target_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_steps": report.total,
            "yaml_reuse": report.yaml_reuse_count,
            "human_resolved": report.human_count,
            "unresolved": len(report.missing),
        },
        "steps": steps_data,
        "unresolved": missing_data,
    }


# ── 核心流水线 ───────────────────────────────────────────────────────────────

def _resolve_with_yaml_reuse(
    step: ExtractedStep,
    page,
    elements_yaml_dir: str,
) -> Optional[ResolvedElement]:
    """阶段1：在已有 yaml 中查匹配，verifier 确认仍可用。"""
    result = yaml_reuse.find_existing(step.element_desc, elements_yaml_dir)
    if result is None:
        return None
    spec, action = result
    if not is_unique(page, spec):
        _logger.info("yaml 复用命中但 verify 失败（selector 可能已变更）：%r", step.element_desc)
        return None
    _logger.info("yaml 复用成功：%r", step.element_desc)
    return ResolvedElement(
        element_desc=step.element_desc,
        step_index=step.step_index,
        action=action or step.action,
        value=step.value,
        locator=spec,
        alternatives=[],
        verified=True,
        source="yaml_reuse",
        attempts=0,
    )


def run_pipeline(
    url: str,
    input_file: str,
    output_file: str,
    report_file: Optional[str] = None,
    enable_human_picker: bool = True,
    browser_type: str = "chromium",
    elements_yaml_dir: str = "pages/elements",
    # 兼容旧参数
    max_retries: int = 3,
) -> SelectorReport:
    """
    完整流水线入口。

    Args:
        url: 目标页面 URL。
        input_file: 测试用例文件路径（Markdown 或纯文本）。
        output_file: 输出的元素定位 YAML 路径（pages/elements/*.yaml）。
        report_file: 完整报告 YAML 路径（可选）。
        enable_human_picker: 是否启用人工点选兜底（默认 True）。
        browser_type: Playwright 浏览器类型。
        elements_yaml_dir: 现有元素 yaml 目录（用于复用检查）。
        max_retries: 兼容旧接口，当前未使用。

    Returns:
        SelectorReport 实例。
    """
    _logger.info("=== selector_finder 开始 ===")
    _logger.info("URL: %s", url)
    _logger.info("输入: %s", input_file)

    # Step 1: 提取测试步骤
    steps = extractor.extract_steps_from_file(input_file)
    if not steps:
        _logger.warning("未提取到任何步骤，退出")
        return SelectorReport(test_case_file=input_file, target_url=url)

    report = SelectorReport(test_case_file=input_file, target_url=url)
    reuse_resolved: list[ResolvedElement] = []
    reuse_missing: list[ExtractedStep] = []

    # Step 2: yaml 复用检查（无头浏览器，仅 verifier 校验）
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = getattr(pw, browser_type).launch(headless=True)
            page = browser.new_context().new_page()
            page.set_default_timeout(15_000)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            for step in steps:
                # 场景钩子（关弹窗等预处理）
                scene_hooks.apply_hooks(page, step)

                resolved = _resolve_with_yaml_reuse(step, page, elements_yaml_dir)
                if resolved:
                    reuse_resolved.append(resolved)
                else:
                    reuse_missing.append(step)

            browser.close()
    except Exception as e:
        _logger.warning("yaml 复用阶段异常（降级为全量人工）: %s", e)
        reuse_missing = list(steps)
        reuse_resolved = []

    report.resolved.extend(reuse_resolved)

    # Step 3: 人工点选（针对复用未命中的步骤）
    if reuse_missing and enable_human_picker:
        _logger.info("启动人工点选，待处理 %d 个元素...", len(reuse_missing))
        human_results = human_picker.pick_missing(url, reuse_missing, browser_type)
        picked_indices = {r.step_index for r in human_results}
        report.missing = [s for s in reuse_missing if s.step_index not in picked_indices]
        report.resolved.extend(human_results)
    elif reuse_missing:
        report.missing = reuse_missing

    report.resolved.sort(key=lambda r: r.step_index)

    # Step 4: 写输出文件
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    elements_dict = _to_elements_yaml(report.resolved)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(elements_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    _logger.info("元素 YAML 已写入: %s (%d 条)", output_file, len(elements_dict))

    if report_file:
        report_path = Path(report_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = _to_report_yaml(report, report.resolved)
        with report_path.open("w", encoding="utf-8") as f:
            yaml.dump(report_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        _logger.info("完整报告已写入: %s", report_file)

    _logger.info(
        "=== 完成：yaml_reuse=%d / human=%d / missing=%d ===",
        report.yaml_reuse_count, report.human_count, len(report.missing),
    )
    return report
