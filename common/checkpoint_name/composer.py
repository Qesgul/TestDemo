"""Checkpoint name 自动补全规则引擎。

输入：(Step, Expect, case_id)
输出：NameDecision(name, tier, todo)

5-Tier 规则（按优先级，命中即停）：
  1. step.raw 含 [name: xxx] 显式标签
  2. step.object + expect.field（均在字典中）
  3. 仅 step.object（expect 无 field 或 field 不在字典）
  4. 仅 expect.field（step 无 object），字典 miss 加 TODO
  5. 兜底：step.raw 去编号后前 8 字

不调用任何 LLM API。Tier 5 的 todo 字段由 case-to-code SKILL 内
的 Claude 读取后，由 Claude 本身判断是否能给更好的名字。
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DICT_PATH = Path(__file__).parent.parent / "checkpoint_name_dict.yaml"

_DICT_CACHE: Optional[Dict[str, Any]] = None


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Step:
    idx: int
    verb: str       # 动词："点击" / "选择" / "输入" / "验证" / ...
    object: str     # 宾语："家装" / "标准模式" / ""（空表示无明确宾语）
    raw: str        # 原文（供 Tier 5 使用）


@dataclass
class Expect:
    idx: int
    kind: str               # "value"|"visibility"|"count"|"navigation"|"text"|"boolean"
    field: Optional[str]    # snake_case 字段名
    value: Optional[object] # 期望值
    operator: Optional[str] # ">=" / "==" / "<" / ...
    raw: str                # 原文（供 Tier 5 使用）


@dataclass
class NameDecision:
    name: str
    tier: int                    # 1-5，标记命名来源
    todo: Optional[str] = None   # 非空时需 SKILL/作者介入


# ── Dict 加载 ─────────────────────────────────────────────────────────────────

def load_dict(path: Path = DICT_PATH) -> Dict[str, Any]:
    """加载字典 YAML，进程内缓存（只读一次）。"""
    global _DICT_CACHE
    if _DICT_CACHE is None:
        try:
            with open(path, encoding="utf-8") as f:
                _DICT_CACHE = yaml.safe_load(f) or {}
        except FileNotFoundError:
            _DICT_CACHE = {}
    return _DICT_CACHE


def reset_dict_cache() -> None:
    """测试辅助：清除缓存，让下次 load_dict() 重新读文件。"""
    global _DICT_CACHE
    _DICT_CACHE = None


# ── 主入口 ────────────────────────────────────────────────────────────────────

def compose(step: Step, expect: Expect, case_id: str = "") -> NameDecision:
    """按 Tier 1→5 顺序匹配，命中即返回。"""
    d = load_dict()

    result = _try_tier1(step)
    if result:
        return result

    result = _try_tier2(step, expect, d)
    if result:
        return result

    result = _try_tier3(step, expect, d)
    if result:
        return result

    result = _try_tier4(step, expect, d)
    if result:
        return result

    return _tier5(step, expect)


# ── Tier 1 ────────────────────────────────────────────────────────────────────

def _try_tier1(step: Step) -> Optional[NameDecision]:
    """步骤 raw 中含 [name: xxx] 标签 → 直接使用。"""
    m = re.search(r"\[name:\s*(.+?)\]", step.raw)
    if m:
        return NameDecision(name=m.group(1).strip(), tier=1)
    return None


# ── Tier 2 ────────────────────────────────────────────────────────────────────

def _try_tier2(step: Step, expect: Expect, d: Dict) -> Optional[NameDecision]:
    """step.object 非空 且 expect.field 在字典中 → 组合 name。"""
    if not step.object or not expect.field:
        return None
    field_phrase = _lookup_field(expect.field, d)
    if field_phrase is None:
        return None

    subject = _trim_suffix(step.object, d)

    if expect.kind == "count":
        modifier = _apply_count_modifier(expect.value, expect.operator, d)
        name = f"{field_phrase}{modifier}" if modifier else field_phrase
    elif expect.kind == "text" and expect.value is not None:
        val_str = str(expect.value)[:6]
        name = _combine(subject, field_phrase) + f"为{val_str}"
    else:
        name = _combine(subject, field_phrase)

    return NameDecision(name=name.strip(), tier=2)


# ── Tier 3 ────────────────────────────────────────────────────────────────────

def _try_tier3(step: Step, expect: Expect, d: Dict) -> Optional[NameDecision]:
    """step.object 非空，但 expect.field 为 None 或不在字典 → 用 __defaults__ 谓语。"""
    if not step.object:
        return None
    predicate = _default_predicate(expect.kind, d)
    return NameDecision(name=f"{step.object}{predicate}", tier=3)


# ── Tier 4 ────────────────────────────────────────────────────────────────────

def _try_tier4(step: Step, expect: Expect, d: Dict) -> Optional[NameDecision]:
    """step.object 为空；用 expect.field 生成 name（字典 miss 时加 TODO）。"""
    if not expect.field:
        return None
    field_phrase = _lookup_field(expect.field, d)
    if field_phrase is not None:
        if expect.kind == "count":
            modifier = _apply_count_modifier(expect.value, expect.operator, d)
            name = f"{field_phrase}{modifier}" if modifier else field_phrase
        elif expect.kind == "text" and expect.value is not None:
            val_str = str(expect.value)[:6]
            name = f"{field_phrase}为{val_str}"
        else:
            name = field_phrase
        return NameDecision(name=name, tier=4)

    # 字典 miss → 英文字段名 + 默认谓语 + TODO 提示
    predicate = _default_predicate(expect.kind, d)
    name = f"{expect.field} {predicate}".strip()
    todo = (
        f"# TODO[checkpoint_dict]: {expect.field} "
        f"待补全中文映射到 common/checkpoint_name_dict.yaml"
    )
    return NameDecision(name=name, tier=4, todo=todo)


# ── Tier 5 ────────────────────────────────────────────────────────────────────

def _tier5(step: Step, expect: Expect) -> NameDecision:
    """兜底：步骤原文去编号后前 8 字，附 todo 提示作者或 SKILL 改善。"""
    name = _first_n_chars(step.raw, n=8)
    if not name:
        name = _first_n_chars(expect.raw, n=8)
    todo = (
        f"step: {step.raw!r} | expect: {expect.raw!r} — "
        "自动命名兜底，建议手动改名或补充字典"
    )
    return NameDecision(name=name, tier=5, todo=todo)


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _lookup_field(field: str, d: Dict[str, Any]) -> Optional[str]:
    """从 fields 区完全匹配 snake_case 字段 → 中文短语。"""
    return d.get("fields", {}).get(field)


def _default_predicate(kind: str, d: Dict[str, Any]) -> str:
    """从 __defaults__ 区查断言类型的默认谓语（缺失时返回 kind 本身）。"""
    return d.get("__defaults__", {}).get(kind, kind)


def _apply_count_modifier(value: object, operator: Optional[str],
                           d: Dict[str, Any]) -> str:
    """根据 count_modifiers 模板生成数值修饰（如 '达到 30'）。"""
    if operator is None or value is None:
        return ""
    template = d.get("count_modifiers", {}).get(operator, "")
    return template.format(n=value) if template else str(value)


def _trim_suffix(subject: str, d: Dict[str, Any]) -> str:
    """主语末字在 trim_suffixes 中 → 删去该末字（如 '搜索框' → '搜索'）。"""
    s = subject.strip()
    for sfx in d.get("trim_suffixes", []):
        if s.endswith(sfx):
            s = s[: -len(sfx)].strip()
            break
    return s


def _combine(subject: str, field_phrase: str) -> str:
    """拼接主语 + 谓语，若 field_phrase 已以 subject 开头则不重复。"""
    if subject and not field_phrase.startswith(subject):
        return f"{subject}{field_phrase}"
    return field_phrase


def _clean_raw(raw: str) -> str:
    """去掉前导编号（'1. ' / '2、' / '（1）'）和引号括号内容。"""
    s = re.sub(r"^[\d]+[\.、。]\s*", "", raw.strip())
    s = re.sub(r"^[（(][\d]+[）)]\s*", "", s)
    s = re.sub(r'["""\'‘’「」《》【】]', "", s)
    return s.strip()


def _first_n_chars(raw: str, n: int = 8) -> str:
    """取 raw 去前导编号后的前 n 个 Unicode 字符。"""
    return _clean_raw(raw)[:n]
