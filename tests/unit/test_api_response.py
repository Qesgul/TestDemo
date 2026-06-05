# -*- coding: utf-8 -*-
def test_api_base_url_fallback_to_origin():
    # settings.yaml 中 api.base_url 为空 → 回退当前环境 base_url 的 origin
    from common.api.config import api_base_url
    assert api_base_url() == "https://www.znzmo.com"


def test_api_response_wraps_raw():
    from common.api.response import ApiResponse

    class Raw:
        status = 200
        ok = True
        headers = {"x": "1"}
        def json(self): return {"code": 0}
        def text(self): return "{}"

    r = ApiResponse(Raw(), elapsed_ms=12, request_method="GET", request_url="/x")
    assert r.status == 200 and r.ok is True and r.elapsed_ms == 12
    assert r.json() == {"code": 0}
    assert r.text == "{}"
    assert r.headers["x"] == "1"
    assert r.request_method == "GET" and r.request_url == "/x"
