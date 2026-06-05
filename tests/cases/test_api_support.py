# -*- coding: utf-8 -*-
"""API 能力运行期 smoke（不连网、不开浏览器）+ 示例用例（默认 skip）。"""
import pytest


def test_api_exports():
    from common.api import ApiClient, ApiResponse, ApiAssertion
    assert ApiClient and ApiResponse and ApiAssertion


def test_api_client_fixture_no_browser(api_client):
    """api_client 应能在不启动浏览器的前提下创建（创建 request context 不拉起浏览器）。"""
    from common.api import ApiClient
    assert isinstance(api_client, ApiClient)


def test_api_assert_fixture(api_assert):
    from common.api import ApiAssertion
    assert isinstance(api_assert, ApiAssertion)


@pytest.mark.skip(reason="示例：真实接口路径待补，去掉 skip 并改成实际接口后启用")
def test_demo_group_list(api_client, api_assert):
    resp = api_client.get("/api/group/list", params={"type": "all"})
    api_assert.status_ok(resp, name="分组列表接口可用")
    api_assert.json_path(resp, "code", 0, name="业务码为0")
