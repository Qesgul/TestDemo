"""
已有 YAML 元素 key 复用：先查是否有匹配 key，通过 verifier 确认仍可用。

规范化规则（匹配时不区分大小写）：
  1. 去 step[N]_ 前缀（如 step1_、step2_）
  2. 去中英文引号
  3. 去括号（含内容）
  4. 去空白 / 下划线 / 连字符 / 标点
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from common.selector_finder.models import LocatorSpec

_logger = logging.getLogger(__name__)


# ── 规范化 ──────────────────────────────────────────────────────────────────

_RE_STEP_PREFIX = re.compile(r"^step\d+_", re.I)
_RE_QUOTES = re.compile(r'[“”‘’"「」『』\'`]')
_RE_BRACKETS = re.compile(r"[（(（(][^）)）)]*[）)）)]")
_RE_NOISE = re.compile(r"[\s_\-。，,.、：:！!？?]")


def _normalize(text: str) -> str:
    s = _RE_STEP_PREFIX.sub("", text)
    s = _RE_QUOTES.sub("", s)
    s = _RE_BRACKETS.sub("", s)
    s = _RE_NOISE.sub("", s)
    return s.lower()


# ── YAML dict → LocatorSpec ─────────────────────────────────────────────────

def _yaml_dict_to_spec(val: Any) -> Optional[LocatorSpec]:
    """将 YAML 条目（字符串或字典）转换为 LocatorSpec。"""
    if isinstance(val, str):
        # 旧格式：字符串直接作为 CSS selector
        return LocatorSpec(strategy="css", selector=val)
    if not isinstance(val, dict):
        return None

    t = val.get("type", "css")
    scope = val.get("scope")

    if t == "css":
        return LocatorSpec(strategy="css", selector=val.get("selector", ""), scope=scope)
    if t == "role":
        return LocatorSpec(
            strategy="role",
            role=val.get("role"),
            name=val.get("name"),
            exact=bool(val.get("exact", False)),
            scope=scope,
        )
    if t == "text":
        return LocatorSpec(
            strategy="text",
            text=val.get("text"),
            exact=bool(val.get("exact", True)),
            scope=scope,
        )
    if t in ("label", "get_by_label"):
        return LocatorSpec(strategy="label", label=val.get("label"), exact=bool(val.get("exact", False)), scope=scope)
    if t == "placeholder":
        return LocatorSpec(strategy="placeholder", placeholder=val.get("placeholder"), scope=scope)
    if t in ("test_id", "testId"):
        return LocatorSpec(strategy="test_id", test_id=val.get("test_id") or val.get("testId"), scope=scope)
    if t == "alt_text":
        # alt_text 映射为 css 兜底（basepage 已支持，这里当 css）
        return LocatorSpec(strategy="css", selector=f"[alt='{val.get('alt_text', '')}']", scope=scope)
    # 未知 type 降级 css
    return LocatorSpec(strategy="css", selector=str(val), scope=scope)


# ── 主接口 ──────────────────────────────────────────────────────────────────

def _load_yaml_keys(yaml_file: Path) -> list[tuple[str, LocatorSpec, str | None]]:
    """
    读取一个 yaml 文件，返回 (normalized_key, LocatorSpec, action) 元组列表。
    """
    try:
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
    except Exception as e:
        _logger.debug("读取 yaml 失败 %s: %s", yaml_file, e)
        return []

    if not isinstance(data, dict):
        return []

    results = []
    for key, val in data.items():
        spec = _yaml_dict_to_spec(val)
        if spec is None:
            continue
        action = val.get("action") if isinstance(val, dict) else None
        results.append((_normalize(str(key)), spec, action))
    return results


def find_existing(
    element_desc: str,
    elements_yaml_dir: str = "pages/elements",
) -> Optional[tuple[LocatorSpec, str | None]]:
    """
    在 pages/elements/*.yaml 中按规范化名称匹配 element_desc。

    Returns:
        (LocatorSpec, action_or_None) 元组，或 None（未找到匹配）。
    """
    norm_target = _normalize(element_desc)
    if not norm_target:
        return None

    yaml_dir = Path(elements_yaml_dir)
    if not yaml_dir.exists():
        return None

    for yaml_file in sorted(yaml_dir.glob("*.yaml")):
        for norm_key, spec, action in _load_yaml_keys(yaml_file):
            # 精确匹配 或 包含匹配（目标是 key 的子串，或 key 是目标的子串）
            if norm_key == norm_target or norm_target in norm_key or norm_key in norm_target:
                _logger.info(
                    "yaml 复用命中：%r → %s (%s)",
                    element_desc, yaml_file.name, spec.strategy,
                )
                return spec, action

    return None


def load_few_shot_examples(
    elements_yaml_dir: str = "pages/elements",
    max_examples: int = 5,
) -> str:
    """
    加载已有 yaml 中的稳定 selector 作为 few-shot 示例文本。
    优先选 test_id / role / 带 # 前缀的 css（稳定 ID）。
    """
    yaml_dir = Path(elements_yaml_dir)
    if not yaml_dir.exists():
        return ""

    examples: list[str] = []
    for yaml_file in sorted(yaml_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            if len(examples) >= max_examples:
                break
            spec = _yaml_dict_to_spec(val)
            if spec is None:
                continue
            # 优先稳定类型
            if spec.strategy == "test_id":
                examples.append(f"  # {key}\n  type: test_id\n  test_id: {spec.test_id}")
            elif spec.strategy == "role" and spec.name:
                examples.append(f"  # {key}\n  type: role\n  role: {spec.role}\n  name: {spec.name}")
            elif spec.strategy == "css" and spec.selector and spec.selector.startswith("#"):
                examples.append(f"  # {key}\n  type: css\n  selector: {spec.selector}")

    return "\n".join(examples) if examples else ""


def find_existing_batch(
    descs: list[str],
    elements_yaml_dir: str = "pages/elements",
) -> dict[str, tuple[LocatorSpec, str | None]]:
    """
    批量在 pages/elements/*.yaml 中按规范化名称匹配多个 element_desc。

    一次性扫描所有 yaml 文件，避免对 N 个元素重复加载 yaml。

    Args:
        descs: 元素描述列表
        elements_yaml_dir: yaml 目录

    Returns:
        dict[desc, (LocatorSpec, action)] — 只包含命中的 desc，未命中不出现在 dict 中
    """
    if not descs:
        return {}

    yaml_dir = Path(elements_yaml_dir)
    if not yaml_dir.exists():
        return {}

    # 一次性加载所有 yaml key
    all_entries: list[tuple[str, LocatorSpec, str | None]] = []
    for yaml_file in sorted(yaml_dir.glob("*.yaml")):
        all_entries.extend(_load_yaml_keys(yaml_file))

    result: dict[str, tuple[LocatorSpec, str | None]] = {}
    for desc in descs:
        norm_target = _normalize(desc)
        if not norm_target:
            continue
        for norm_key, spec, action in all_entries:
            if norm_key == norm_target or norm_target in norm_key or norm_key in norm_target:
                result[desc] = (spec, action)
                _logger.info("yaml 复用批量命中：%r → %s", desc, spec.strategy)
                break  # 第一个命中
    return result
