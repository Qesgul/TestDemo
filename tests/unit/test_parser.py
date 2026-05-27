"""Unit tests for common/checkpoint_name/parser.py。

运行: pytest tests/unit/test_parser.py -v
"""
import pytest
from common.checkpoint_name.parser import (
    split_numbered_items, parse_step, parse_expect, parse_pairs,
)
from common.checkpoint_name.composer import Step, Expect


# ══════════════════════════════════════════════════════════════
# split_numbered_items
# ══════════════════════════════════════════════════════════════

def test_split_dot_numbered_multiline():
    items = split_numbered_items("1. 点击家装\n2. 选择标准模式\n3. 验证结果")
    assert items == [(1, "点击家装"), (2, "选择标准模式"), (3, "验证结果")]

def test_split_chinese_semicolon():
    items = split_numbered_items("1. 点击家装；2. 查看结果")
    assert items == [(1, "点击家装"), (2, "查看结果")]

def test_split_no_number_returns_idx_1():
    items = split_numbered_items("点击家装")
    assert items == [(1, "点击家装")]

def test_split_parenthesis_number():
    items = split_numbered_items("（1）点击家装\n（2）查看结果")
    assert items == [(1, "点击家装"), (2, "查看结果")]

def test_split_arabic_comma_number():
    items = split_numbered_items("1、点击家装\n2、查看结果")
    assert items == [(1, "点击家装"), (2, "查看结果")]


# ══════════════════════════════════════════════════════════════
# parse_step
# ══════════════════════════════════════════════════════════════

def test_parse_step_click_verb_and_object():
    s = parse_step(1, "点击家装")
    assert s.verb == "点击"
    assert s.object == "家装"
    assert s.idx == 1

def test_parse_step_select_strips_quotes():
    s = parse_step(2, "选择「标准模式」")
    assert s.verb == "选择"
    assert s.object == "标准模式"

def test_parse_step_input_with_trailing_words():
    s = parse_step(3, "输入搜索框关键词")
    assert s.verb == "输入"
    assert "搜索" in s.object

def test_parse_step_wait_no_business_object():
    """纯等待步骤，宾语为空（纯数字/单位部分被清空）。"""
    s = parse_step(4, "等待 3 秒")
    assert s.verb == "等待"
    assert s.object == ""

def test_parse_step_stores_raw():
    s = parse_step(1, "点击家装详情按钮")
    assert s.raw == "点击家装详情按钮"


# ══════════════════════════════════════════════════════════════
# parse_expect
# ══════════════════════════════════════════════════════════════

def test_parse_expect_snake_case_eq():
    e = parse_expect(1, "cost_standard == 6")
    assert e.kind == "value"
    assert e.field == "cost_standard"
    assert e.value == 6
    assert e.operator == "=="

def test_parse_expect_snake_case_gte():
    e = parse_expect(1, "cards >= 30")
    assert e.field == "cards"
    assert e.value == 30
    assert e.operator == ">="

def test_parse_expect_visibility_keyword():
    e = parse_expect(1, "商品价格显示")
    assert e.kind == "visibility"

def test_parse_expect_navigation_keyword():
    e = parse_expect(1, "跳转到家装详情页")
    assert e.kind == "navigation"

def test_parse_expect_text_keyword():
    e = parse_expect(1, 'VIP 按钮文案为"续费"')
    assert e.kind == "text"
    assert e.value is not None
    assert "续费" in str(e.value)

def test_parse_expect_stores_raw():
    e = parse_expect(1, "cost_standard == 6")
    assert e.raw == "cost_standard == 6"


# ══════════════════════════════════════════════════════════════
# parse_pairs
# ══════════════════════════════════════════════════════════════

def test_parse_pairs_aligns_by_index():
    steps = "1. 点击家装\n2. 验证消耗"
    expects = "1. 跳转到家装\n2. cost_standard == 6"
    pairs = parse_pairs(steps, expects)
    assert len(pairs) == 2
    s1, e1 = pairs[0]
    s2, e2 = pairs[1]
    assert s1.object == "家装"
    assert e2.field == "cost_standard"

def test_parse_pairs_single_no_number():
    pairs = parse_pairs("进入图钉新品页", "页面正常加载")
    assert len(pairs) == 1
    step, expect = pairs[0]
    assert step.idx == 1 and expect.idx == 1
