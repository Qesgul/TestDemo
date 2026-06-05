# -*- coding: utf-8 -*-
import pytest


class _Resp:
    def __init__(self, status=200, body=None):
        self.status = status
        self._body = body if body is not None else {}
        self.request_method = "GET"
        self.request_url = "/x"
        self.request_body = None
        self.headers = {}
        self.elapsed_ms = 5

    @property
    def text(self):
        return "{}"

    def json(self):
        return self._body


def test_api_assert_status_ok_pass():
    from common.api.assertions import ApiAssertion
    a = ApiAssertion("t")
    a.status_ok(_Resp(status=200), name="接口可用")
    assert a._checkpoints[0].status == "PASS"
    assert a._checkpoints[0].name == "接口可用"


def test_api_assert_json_path_nested_list_pass():
    from common.api.assertions import ApiAssertion
    a = ApiAssertion("t")
    a.json_path(_Resp(body={"data": [{"group_name": "默认分组"}]}),
                "data.0.group_name", "默认分组", name="首个分组名")
    assert a._checkpoints[0].status == "PASS"


def test_api_assert_json_path_fail_records_and_raises():
    from common.api.assertions import ApiAssertion
    from common.assertions import disable_diagnostics, enable_diagnostics
    a = ApiAssertion("t")
    disable_diagnostics()
    try:
        with pytest.raises(AssertionError):
            a.json_path(_Resp(body={"code": 1}), "code", 0, name="业务码")
    finally:
        enable_diagnostics()
    assert a._checkpoints[0].status == "FAIL"
    assert a._checkpoints[0].error_msg is not None


def test_api_assert_shares_checkpoint_summary(capsys):
    from common.api.assertions import ApiAssertion
    a = ApiAssertion("t")
    a.status_ok(_Resp(status=200), name="接口可用")
    a.print_summary(tw=None)
    out = capsys.readouterr().out
    assert "关键校验点汇总" in out and "接口可用" in out
