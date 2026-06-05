# -*- coding: utf-8 -*-
class _FakeRaw:
    status = 200
    ok = True
    headers = {}
    def json(self): return {}
    def text(self): return ""


def test_api_client_joins_base_url_and_dispatches():
    from common.api.client import ApiClient
    calls = {}

    class FakeRC:
        def fetch(self, url, **kw):
            calls["url"] = url
            calls["kw"] = kw
            return _FakeRaw()

    client = ApiClient(FakeRC(), base_url="https://api.test", default_headers={}, timeout_ms=1000)
    resp = client.get("/v1/items", params={"a": 1})
    assert calls["url"] == "https://api.test/v1/items"
    assert calls["kw"]["method"] == "GET"
    assert calls["kw"]["params"] == {"a": 1}
    assert resp.status == 200 and resp.request_method == "GET"


def test_api_client_json_maps_to_data():
    from common.api.client import ApiClient
    captured = {}

    class FakeRC:
        def fetch(self, url, **kw):
            captured.update(kw)
            return _FakeRaw()

    client = ApiClient(FakeRC(), base_url="https://api.test", default_headers={}, timeout_ms=1000)
    client.post("/x", json={"k": "v"})
    assert captured.get("data") == {"k": "v"}
    assert "json" not in captured


def test_api_client_absolute_url_passthrough():
    from common.api.client import ApiClient
    calls = {}

    class FakeRC:
        def fetch(self, url, **kw):
            calls["url"] = url
            return _FakeRaw()

    client = ApiClient(FakeRC(), base_url="https://api.test", default_headers={"Accept": "x"}, timeout_ms=1000)
    client.get("https://other.test/abs")
    assert calls["url"] == "https://other.test/abs"
