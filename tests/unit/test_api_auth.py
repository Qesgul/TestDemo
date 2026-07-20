# -*- coding: utf-8 -*-
def test_load_storage_state_shape(monkeypatch):
    import common.api.auth as auth
    monkeypatch.setattr(auth, "_default_account", lambda: "acc")
    monkeypatch.setattr(auth.CookieManager, "load_cookies",
                        lambda account, **kw: {"cookies": [{"name": "x", "value": "1"}], "timestamp": "t"})
    monkeypatch.setattr(auth.CookieManager, "is_cookie_valid", lambda data, **kw: True)
    ss = auth.load_storage_state()
    assert ss == {"cookies": [{"name": "x", "value": "1"}], "origins": []}


def test_load_storage_state_none_when_no_cookie(monkeypatch):
    import common.api.auth as auth
    monkeypatch.setattr(auth, "_default_account", lambda: "acc")
    monkeypatch.setattr(auth.CookieManager, "load_cookies", lambda account, **kw: None)
    assert auth.load_storage_state() is None


def test_load_storage_state_none_when_no_account(monkeypatch):
    import common.api.auth as auth
    monkeypatch.setattr(auth, "_default_account", lambda: None)
    assert auth.load_storage_state() is None


# ===== 服务端验活 verify_session_alive =====
class _FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def json(self):
        return self._body


class _FakeRequest:
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    def get(self, url, **kw):
        if self._exc:
            raise self._exc
        return self._resp


class _FakeCtx:
    def __init__(self, resp=None, exc=None):
        self.request = _FakeRequest(resp, exc)


def test_verify_session_alive_logged_in():
    import common.api.auth as auth
    ctx = _FakeCtx(resp=_FakeResp(200, {"error": {"errorCode": "0"}, "data": 11}))
    assert auth.verify_session_alive(ctx) is True


def test_verify_session_alive_logged_out():
    import common.api.auth as auth
    ctx = _FakeCtx(resp=_FakeResp(200, {"error": {"errorCode": "00005",
                                                   "errorMsg": "没有登录"}, "data": None}))
    assert auth.verify_session_alive(ctx) is False


def test_verify_session_alive_non_200():
    import common.api.auth as auth
    ctx = _FakeCtx(resp=_FakeResp(502, {}))
    assert auth.verify_session_alive(ctx) is False


def test_verify_session_alive_exception_is_false():
    import common.api.auth as auth
    ctx = _FakeCtx(exc=RuntimeError("network down"))
    assert auth.verify_session_alive(ctx) is False
