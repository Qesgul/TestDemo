"""Unit tests for common/tracking/expectations.py。

运行: pytest tests/unit/test_gio_expectations.py -v
"""
from common.tracking.expectations import (
    GioExpectation, load_gio_expectations, parse_tracking_section,
)


_SECTION = {
    "requirement": "充值测试埋点（已上线）",
    "events": [
        {"identifier": "sc_coinrecharge_show", "name": "曝光",
         "trigger": "点充值按钮", "expect_vars": {"data1": "1"}},
        {"identifier": "Rechargetest_2", "name": "登录变量",
         "groups": ["实验组", "对照组"]},
        {"identifier": "sc_coinrecharge_pay", "name": "支付成功",
         "status": "pending"},
    ],
}


def test_parse_returns_expectations():
    exps = parse_tracking_section(_SECTION)
    assert [e.identifier for e in exps] == [
        "sc_coinrecharge_show", "Rechargetest_2", "sc_coinrecharge_pay",
    ]


def test_expectation_defaults():
    exps = parse_tracking_section(_SECTION)
    show = exps[0]
    assert show.expect_vars == {"data1": "1"}
    assert show.status == "active"
    assert show.groups == []


def test_pending_status_parsed():
    exps = parse_tracking_section(_SECTION)
    pay = exps[2]
    assert pay.status == "pending"


def test_groups_parsed():
    exps = parse_tracking_section(_SECTION)
    assert exps[1].groups == ["实验组", "对照组"]


def test_parse_missing_events_returns_empty():
    assert parse_tracking_section({"requirement": "x"}) == []
    assert parse_tracking_section(None) == []


def test_load_from_recharge_yaml():
    exps = load_gio_expectations("tests/data/recharge_flow_data.yaml")
    ids = {e.identifier for e in exps}
    assert "sc_coinrecharge_show" in ids
    assert "sc_coinrecharge_pay" in ids
