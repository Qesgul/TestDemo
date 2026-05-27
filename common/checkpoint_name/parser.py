"""Markdown 测试步骤 / 预期结果解析器。

从 Markdown 用例表格的「测试步骤」和「预期结果」两列文本里提取结构化的
Step 和 Expect 对象，供 composer.compose() 使用。

单条步骤格式（常见变体）：
  "1. 点击家装"  "1、选择「标准模式」"  "（1）输入搜索关键词"

单条预期格式（优先级从高到低）：
  "cost_standard == 6"   → kind=value,  field=cost_standard, operator===, value=6
  "商品价格显示"          → kind=visibility
  "卡片数量 >= 30"        → kind=count,  operator=>=, value=30
  "跳转到详情页"          → kind=navigation
  '按钮文案为"续费"'      → kind=text,   value=续费
  （其余兜底）           → kind=visibility
"""
from __future__ import annotations
import re
from typing import List, Optional, Tuple

from common.checkpoint_name.composer import Step, Expect

# ── 动词识别表（顺序敏感：长匹配优先）────────────────────────────────────────
_VERBS = [
    "点击", "单击", "选择", "选中", "输入", "填写", "清空",
    "拖拽", "悬停", "右键", "双击", "检查", "验证", "查看",
    "等待", "进入", "进到", "跳转", "滚动", "切换", "关闭",
    "打开", "刷新",
]

# ── 可见性关键词 ───────────────────────────────────────────────────────────────
_VISIBILITY_WORDS = {"显示", "可见", "出现", "存在", "展示", "呈现"}

# ── 导航关键词 ────────────────────────────────────────────────────────────────
_NAVIGATION_WORDS = {"跳转", "进入", "导航", "重定向", "加载", "跳到"}


def split_numbered_items(text: str) -> List[Tuple[int, str]]:
    """把多行编号列表拆成 [(idx, content), ...] 列表。

    支持格式：
      "1. xxx" / "1、xxx" / "（1）xxx" / "1。xxx"
    无编号时整体作为 idx=1。
    中文分号 `；` 等同换行。
    """
    items: List[Tuple[int, str]] = []
    # 先把中文分号和换行统一为 \n
    normalized = re.sub(r"[；]", "\n", text)
    lines = [ln.strip() for ln in normalized.splitlines() if ln.strip()]
    for line in lines:
        m = re.match(r"^[（(]?(\d+)[)）\.、。]\s*(.+)$", line)
        if m:
            items.append((int(m.group(1)), m.group(2).strip()))
        else:
            next_idx = (items[-1][0] + 1) if items else 1
            items.append((next_idx, line))
    return items


def parse_step(idx: int, raw: str) -> Step:
    """从步骤原文提取 verb 和 object。

    例：
      "点击家装"          → verb="点击", object="家装"
      "选择「标准模式」"  → verb="选择", object="标准模式"
      "等待 3 秒"         → verb="等待", object=""
    """
    # 去装饰性引号和括号内容
    cleaned = re.sub(r'["""\'''「」《》【】]', "", raw.strip())
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", cleaned).strip()

    verb = ""
    obj = cleaned
    for v in _VERBS:
        if cleaned.startswith(v):
            verb = v
            obj = cleaned[len(v):].strip()
            break

    # 纯数字/单位的宾语清空（"等待 3 秒" → obj=""）
    if re.match(r"^[\d\s秒分钟毫秒ms]+$", obj):
        obj = ""

    return Step(idx=idx, verb=verb, object=obj, raw=raw)


def parse_expect(idx: int, raw: str) -> Expect:
    """从预期原文提取 kind / field / value / operator。

    优先级（高→低）：
      1. snake_case 字段 + 比较运算符（"cost_standard == 6"）
      2. 可见性关键词（"商品价格显示"）
      3. 导航关键词（"跳转到详情页"）
      4. 文案关键词（"按钮文案为续费"）
      5. 数量表达式（">= 30"）
      6. 兜底 → visibility
    """
    s = raw.strip()

    # 1. snake_case 字段 + 比较运算符
    m = re.match(r"^([a-z][a-z0-9_]*)\s*(>=|<=|==|!=|>|<)\s*(.+)$", s)
    if m:
        field = m.group(1)
        operator = m.group(2)
        val_str = m.group(3).strip().strip('"\'')
        value: object
        try:
            value = int(val_str)
        except ValueError:
            try:
                value = float(val_str)
            except ValueError:
                value = val_str
        kind = "count" if re.search(r"\b(数量|count|cards|个数)\b", field) else "value"
        return Expect(idx=idx, kind=kind, field=field, value=value,
                      operator=operator, raw=raw)

    # 2. 可见性关键词
    for word in _VISIBILITY_WORDS:
        if word in s:
            field = _extract_subject(s, word)
            return Expect(idx=idx, kind="visibility", field=field,
                          value=None, operator=None, raw=raw)

    # 3. 导航关键词
    if any(w in s for w in _NAVIGATION_WORDS):
        return Expect(idx=idx, kind="navigation", field="url",
                      value=None, operator=None, raw=raw)

    # 4. 文案关键词（"xxx 文案为 yyy"）
    m_text = re.search(r"文案[为是](.+)$", s)
    if m_text:
        return Expect(idx=idx, kind="text", field="btn_text",
                      value=m_text.group(1).strip().strip('"\''),
                      operator=None, raw=raw)

    # 5. 纯数量表达式（">= 30" 无 snake_case 前缀）
    m_count = re.search(r"(>=|<=|==|>|<)\s*(\d+)", s)
    if m_count:
        return Expect(idx=idx, kind="count", field=None,
                      value=int(m_count.group(2)),
                      operator=m_count.group(1), raw=raw)

    # 6. 兜底 → visibility
    return Expect(idx=idx, kind="visibility", field=None,
                  value=None, operator=None, raw=raw)


def _extract_subject(text: str, stop_word: str) -> Optional[str]:
    """从 '结果列表显示' 提取 '结果列表'（stop_word 前的中文主语）。"""
    idx = text.find(stop_word)
    if idx <= 0:
        return None
    subject = text[:idx].strip()
    subject = re.sub(r"^(页面|界面|当前|下方|上方)", "", subject).strip()
    return subject if subject else None


def parse_pairs(steps_text: str, expects_text: str) -> List[Tuple[Step, Expect]]:
    """把步骤列和预期列按编号对齐，返回 [(Step, Expect), ...]。"""
    step_map = {idx: content for idx, content in split_numbered_items(steps_text)}
    expect_map = {idx: content for idx, content in split_numbered_items(expects_text)}

    all_idxs = sorted(set(step_map) | set(expect_map))
    pairs: List[Tuple[Step, Expect]] = []
    for i in all_idxs:
        step_raw = step_map.get(i, "")
        expect_raw = expect_map.get(i, "")
        pairs.append((parse_step(i, step_raw), parse_expect(i, expect_raw)))
    return pairs
