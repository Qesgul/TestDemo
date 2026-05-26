"""
测试用例文本 → ExtractedStep 列表。

使用规则解析，支持编号列表和 Markdown 表格格式，无外部依赖。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from common.selector_finder.models import ExtractedStep

_logger = logging.getLogger(__name__)

# 动作关键词优先级（先 fill/select，再 click，避免"点击选择"误判）
_ACTION_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"上传|upload", re.I), "upload"),
    (re.compile(r"输入|填写|填入|键入", re.I), "fill"),
    (re.compile(r"选择|选中|勾选|选取", re.I), "select"),
    (re.compile(r"悬停|hover", re.I), "hover"),
    (re.compile(r"断言|验证|确认|检查|expect|assert", re.I), "assert"),
    (re.compile(r"点击|单击|双击|click|tap", re.I), "click"),
]

_ACTION_PREFIX_RE = re.compile(
    r"^(点击|单击|双击|上传|输入|填写|填入|选择|选中|勾选|悬停|验证|断言|确认|检查)\s*",
    re.I,
)

# 提取 fill/select 值：引号或书名号包裹的内容
_QUOTED_VALUE_RE = re.compile(r'[「『"\'"]([^」』"\'"\n]{1,60})[」』"\'"]')

# 编号行：1. / 1、/ (1) / 第1步：等
_NUMBERED_LINE_RE = re.compile(
    r"^(?:\d+\s*[.、）)]\s*|[（(]\s*\d+\s*[）)]\s*|第\s*\d+\s*[步骤]\s*[：:.]?\s*)(.+)$"
)

_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^[\|\s\-:]+$")
_HEADER_KEYWORDS_RE = re.compile(r"步骤|编号|序号|操作|动作|说明|用例|标题|前置|预期|结果|优先")


def _infer_action(text: str) -> str:
    for pattern, action in _ACTION_MAP:
        if pattern.search(text):
            return action
    return "click"


def _extract_value(text: str, action: str) -> Optional[str]:
    if action not in ("fill", "select"):
        return None
    m = _QUOTED_VALUE_RE.search(text)
    return m.group(1).strip() if m else None


def _clean_element_desc(text: str) -> str:
    return _ACTION_PREFIX_RE.sub("", text).strip()


def _make_step(text: str, index: int) -> ExtractedStep:
    action = _infer_action(text)
    return ExtractedStep(
        step_index=index,
        description=text,
        action=action,
        element_desc=_clean_element_desc(text),
        value=_extract_value(text, action),
    )


def _parse_numbered_list(lines: list[str]) -> list[ExtractedStep]:
    steps: list[ExtractedStep] = []
    for line in lines:
        m = _NUMBERED_LINE_RE.match(line.strip())
        if m:
            steps.append(_make_step(m.group(1).strip(), len(steps) + 1))
    return steps


def _parse_markdown_table(lines: list[str]) -> list[ExtractedStep]:
    steps: list[ExtractedStep] = []
    in_table = False
    step_col_idx: Optional[int] = None

    for line in lines:
        stripped = line.strip()
        if not _TABLE_ROW_RE.match(stripped):
            in_table = False
            step_col_idx = None
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        # 分隔行
        if _TABLE_SEP_RE.match(stripped.replace("|", " ")):
            continue

        if not in_table:
            # 表头：找"步骤/操作"列索引
            in_table = True
            for i, cell in enumerate(cells):
                if re.search(r"步骤|操作|动作", cell):
                    step_col_idx = i
                    break
            continue

        # 数据行
        if step_col_idx is not None and step_col_idx < len(cells):
            content = cells[step_col_idx]
        else:
            # 没有明确列索引：找首个含动作词的单元格
            content = next(
                (c for c in cells if _infer_action(c) != "click" or re.search(r"点击|单击|click|tap", c) if len(c) >= 3),
                "",
            )

        if not content or _HEADER_KEYWORDS_RE.search(content):
            continue

        # 单元格内可能包含多步（分号分隔）
        for sub in re.split(r"[；;]\s*", content):
            sub = sub.strip()
            if len(sub) >= 2:
                steps.append(_make_step(sub, len(steps) + 1))

    return steps


def extract_steps(test_case_text: str) -> list[ExtractedStep]:
    """从测试用例文本解析结构化步骤列表。"""
    lines = test_case_text.splitlines()

    # 编号列表优先
    steps = _parse_numbered_list(lines)
    if steps:
        _logger.info("从编号列表提取到 %d 个步骤", len(steps))
        return steps

    # 退回 Markdown 表格
    steps = _parse_markdown_table(lines)
    if steps:
        _logger.info("从 Markdown 表格提取到 %d 个步骤", len(steps))
    else:
        _logger.warning("未能从文本中提取到任何步骤，请检查格式（编号列表或 Markdown 表格）")

    return steps


def extract_steps_from_file(path: str) -> list[ExtractedStep]:
    """从文件读取测试用例文本并提取步骤。"""
    text = Path(path).read_text(encoding="utf-8")
    return extract_steps(text)
