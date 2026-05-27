"""Unit tests for common/checkpoint_name/composer.py — Checkpoint name 自动补全规则引擎。

运行: pytest tests/unit/test_composer.py -v
"""
import pytest
from pathlib import Path
from common.checkpoint_name.composer import (
    Step, Expect, NameDecision,
    compose, load_dict, reset_dict_cache,
    _try_tier1, _try_tier2, _try_tier3, _try_tier4, _tier5,
    _lookup_field, _default_predicate, _apply_count_modifier,
    _trim_suffix, _combine, _first_n_chars, _clean_raw,
)

REAL_DICT_PATH = Path("common/checkpoint_name_dict.yaml")


@pytest.fixture(autouse=True)
def fresh_dict():
    """每个测试前清除缓存，保证字典从磁盘重新读取。"""
    reset_dict_cache()
    yield
    reset_dict_cache()


# ══════════════════════════════════════════════════════════════
# Dataclass 基础
# ══════════════════════════════════════════════════════════════

def test_step_fields():
    s = Step(idx=1, verb="点击", object="家装", raw="1. 点击家装")
    assert s.idx == 1 and s.verb == "点击" and s.object == "家装"

def test_expect_fields():
    e = Expect(idx=2, kind="value", field="cost_standard", value=6,
               operator="==", raw="cost_standard == 6")
    assert e.kind == "value" and e.field == "cost_standard" and e.value == 6

def test_name_decision_todo_defaults_none():
    nd = NameDecision(name="测试名称", tier=2)
    assert nd.todo is None


# ══════════════════════════════════════════════════════════════
# load_dict
# ══════════════════════════════════════════════════════════════

def test_load_dict_returns_dict_with_fields():
    d = load_dict(REAL_DICT_PATH)
    assert isinstance(d, dict)
    assert "fields" in d
    assert "cost_standard" in d["fields"]

def test_load_dict_missing_file_returns_empty():
    reset_dict_cache()
    d = load_dict(Path("nonexistent_dict_zzz.yaml"))
    assert d == {}

def test_load_dict_caches_same_object():
    reset_dict_cache()
    d1 = load_dict(REAL_DICT_PATH)
    d2 = load_dict(REAL_DICT_PATH)
    assert d1 is d2  # 同一对象 → 缓存命中


# ══════════════════════════════════════════════════════════════
# Tier 1: 显式 [name: xxx] 标签
# ══════════════════════════════════════════════════════════════

def test_tier1_explicit_label_in_raw():
    step = Step(idx=2, verb="验证", object="",
                raw="2. 验证消耗点数 [name: 标准模式知点消耗]")
    expect = Expect(idx=2, kind="value", field="cost_standard", value=6,
                    operator="==", raw="cost_standard == 6")
    result = compose(step, expect)
    assert result.tier == 1
    assert result.name == "标准模式知点消耗"
    assert result.todo is None

def test_tier1_label_strips_extra_spaces():
    step = Step(idx=1, verb="点击", object="家装",
                raw="点击家装  [name:  跳转家装详情  ]")
    expect = Expect(idx=1, kind="navigation", field="url",
                    value=None, operator=None, raw="跳转到家装详情页")
    result = compose(step, expect)
    assert result.tier == 1
    assert result.name == "跳转家装详情"

def test_tier1_not_triggered_without_label():
    step = Step(idx=1, verb="点击", object="家装", raw="1. 点击家装")
    assert _try_tier1(step) is None


# ══════════════════════════════════════════════════════════════
# Tier 2: step.object + expect.field 组合
# ══════════════════════════════════════════════════════════════

def test_tier2_field_phrase_starts_with_subject():
    """cost_standard → '标准模式知点消耗'，已包含 subject '标准模式' → 不重复拼接。"""
    step = Step(idx=2, verb="选择", object="标准模式", raw="2. 选择标准模式")
    expect = Expect(idx=2, kind="value", field="cost_standard", value=6,
                    operator="==", raw="cost_standard == 6")
    result = compose(step, expect)
    assert result.tier == 2
    assert result.name == "标准模式知点消耗"

def test_tier2_navigation_url():
    """家装 + url → '家装页面跳转'（subject + field_phrase 拼接）。"""
    step = Step(idx=1, verb="点击", object="家装", raw="1. 点击家装")
    expect = Expect(idx=1, kind="navigation", field="url",
                    value=None, operator=None, raw="跳转到家装详情页")
    result = compose(step, expect)
    assert result.tier == 2
    assert result.name == "家装页面跳转"

def test_tier2_trim_suffix_box():
    """搜索框 → trim '框' → 搜索；搜索 + 结果列表 → '搜索结果列表'。"""
    step = Step(idx=1, verb="输入", object="搜索框", raw="输入搜索框关键词")
    expect = Expect(idx=1, kind="visibility", field="result_list",
                    value=None, operator=None, raw="结果列表显示")
    result = compose(step, expect)
    assert result.tier == 2
    assert result.name == "搜索结果列表"

def test_tier2_text_kind_with_value():
    """VIP 按钮 + btn_text + value='续费' → name 含 '按钮文案' 和 '续费'。"""
    step = Step(idx=1, verb="查看", object="VIP 按钮", raw="查看 VIP 按钮")
    expect = Expect(idx=1, kind="text", field="btn_text", value="续费",
                    operator=None, raw='按钮文案为"续费"')
    result = compose(step, expect)
    assert result.tier == 2
    assert "按钮文案" in result.name
    assert "续费" in result.name

def test_tier2_count_with_gte_modifier():
    """downloads + >= 5 → '下载次数达到 5'（count 类走 field_phrase + modifier）。"""
    step = Step(idx=1, verb="验证", object="下载记录", raw="验证下载记录")
    expect = Expect(idx=1, kind="count", field="downloads", value=5,
                    operator=">=", raw="downloads >= 5")
    result = compose(step, expect)
    assert result.tier == 2
    assert result.name == "下载次数达到 5"

def test_tier2_not_triggered_when_field_not_in_dict():
    step = Step(idx=1, verb="验证", object="家装", raw="验证家装")
    expect = Expect(idx=1, kind="value", field="unknown_field_xyz",
                    value=1, operator="==", raw="unknown_field_xyz == 1")
    assert _try_tier2(step, expect, load_dict(REAL_DICT_PATH)) is None

def test_tier2_not_triggered_when_no_object():
    step = Step(idx=1, verb="等待", object="", raw="等待页面加载")
    expect = Expect(idx=1, kind="value", field="cost_standard",
                    value=6, operator="==", raw="cost_standard == 6")
    assert _try_tier2(step, expect, load_dict(REAL_DICT_PATH)) is None


# ══════════════════════════════════════════════════════════════
# Tier 3: 仅 step.object（expect.field 为 None 或不在字典）
# ══════════════════════════════════════════════════════════════

def test_tier3_object_plus_default_navigation():
    """图钉新品页 + navigation(field=None) → '图钉新品页跳转'。"""
    step = Step(idx=1, verb="进入", object="图钉新品页", raw="1. 进入图钉新品页")
    expect = Expect(idx=1, kind="navigation", field=None,
                    value=None, operator=None, raw="页面正常加载")
    result = compose(step, expect)
    assert result.tier == 3
    assert result.name == "图钉新品页跳转"

def test_tier3_object_plus_default_visibility():
    """图片列表 + visibility(field=None) → '图片列表可见'。"""
    step = Step(idx=2, verb="选择", object="图片列表", raw="选择图片列表")
    expect = Expect(idx=2, kind="visibility", field=None,
                    value=None, operator=None, raw="图片列表出现")
    result = compose(step, expect)
    assert result.tier == 3
    assert result.name == "图片列表可见"

def test_tier3_not_triggered_when_no_object():
    step = Step(idx=1, verb="等待", object="", raw="等待")
    expect = Expect(idx=1, kind="navigation", field=None,
                    value=None, operator=None, raw="加载")
    assert _try_tier3(step, expect, load_dict(REAL_DICT_PATH)) is None


# ══════════════════════════════════════════════════════════════
# Tier 4: 仅 expect.field（step.object 为空）
# ══════════════════════════════════════════════════════════════

def test_tier4_field_in_dict():
    """无 object；price → '商品价格'。"""
    step = Step(idx=3, verb="等待", object="", raw="等待 3 秒")
    expect = Expect(idx=3, kind="visibility", field="price",
                    value=None, operator=None, raw="商品价格显示")
    result = compose(step, expect)
    assert result.tier == 4
    assert result.name == "商品价格"

def test_tier4_count_field_with_modifier():
    """cards + >= 30 → '卡片数量达到 30'。"""
    step = Step(idx=3, verb="验证", object="", raw="验证")
    expect = Expect(idx=3, kind="count", field="cards", value=30,
                    operator=">=", raw="卡片数量 >= 30")
    result = compose(step, expect)
    assert result.tier == 4
    assert "卡片数量" in result.name
    assert "30" in result.name

def test_tier4_dict_miss_adds_checkpoint_dict_todo():
    """字典中不存在的字段 → name 保留英文字段名，todo 含 checkpoint_dict。"""
    step = Step(idx=1, verb="等待", object="", raw="等待")
    expect = Expect(idx=1, kind="value", field="mystery_field_zzz",
                    value=1, operator="==", raw="mystery_field_zzz == 1")
    result = compose(step, expect)
    assert result.tier == 4
    assert "mystery_field_zzz" in result.name
    assert result.todo is not None
    assert "checkpoint_dict" in result.todo


# ══════════════════════════════════════════════════════════════
# Tier 5: 兜底 — 步骤原文前 8 字
# ══════════════════════════════════════════════════════════════

def test_tier5_first_8_chars_of_step_raw():
    """无法匹配 Tier 1-4 → 步骤原文去编号后前 8 字。"""
    step = Step(idx=2, verb="验证", object="",
                raw="2. 验证用户标签下拉框中包含「设计师」选项")
    expect = Expect(idx=2, kind="visibility", field=None,
                    value=None, operator=None, raw="下拉框选项存在")
    result = compose(step, expect)
    assert result.tier == 5
    assert result.name == "验证用户标签下拉"
    assert result.todo is not None

def test_tier5_todo_contains_both_raws():
    step = Step(idx=1, verb="", object="", raw="等待页面响应")
    expect = Expect(idx=1, kind="visibility", field=None,
                    value=None, operator=None, raw="无报错")
    result = _tier5(step, expect)
    assert "等待页面响应" in result.todo
    assert "无报错" in result.todo

def test_tier5_fallback_to_expect_when_step_empty():
    """step.raw 为空 → 取 expect.raw 前 8 字。"""
    step = Step(idx=1, verb="", object="", raw="")
    expect = Expect(idx=1, kind="visibility", field=None,
                    value=None, operator=None, raw="VIP 按钮可见")
    result = _tier5(step, expect)
    assert result.name == "VIP 按钮可见"


# ══════════════════════════════════════════════════════════════
# 辅助函数单测
# ══════════════════════════════════════════════════════════════

def test_trim_suffix_removes_last_char():
    d = {"trim_suffixes": ["框", "按钮", "入口"]}
    assert _trim_suffix("搜索框", d) == "搜索"
    assert _trim_suffix("VIP 按钮", d) == "VIP"
    assert _trim_suffix("家装入口", d) == "家装"
    assert _trim_suffix("标准模式", d) == "标准模式"  # 无后缀 → 不变

def test_apply_count_modifier_operators():
    d = {"count_modifiers": {">=": "达到 {n}", ">": "超过 {n}", "==": "等于 {n}"}}
    assert _apply_count_modifier(30, ">=", d) == "达到 30"
    assert _apply_count_modifier(5, ">", d) == "超过 5"
    assert _apply_count_modifier(10, "==", d) == "等于 10"
    assert _apply_count_modifier(10, None, d) == ""
    assert _apply_count_modifier(None, ">=", d) == ""

def test_clean_raw_strips_leading_numbering():
    assert _clean_raw("1. 点击家装") == "点击家装"
    assert _clean_raw("2、选择标准模式") == "选择标准模式"
    assert _clean_raw("（1）输入关键词") == "输入关键词"
    assert _clean_raw('验证"用户名"显示') == "验证用户名显示"

def test_first_n_chars_unicode():
    raw = "2. 验证用户标签下拉框中包含「设计师」选项"
    assert _first_n_chars(raw, 8) == "验证用户标签下拉"

def test_combine_no_duplication():
    assert _combine("标准模式", "标准模式知点消耗") == "标准模式知点消耗"
    assert _combine("家装", "页面跳转") == "家装页面跳转"
    assert _combine("", "结果列表") == "结果列表"
