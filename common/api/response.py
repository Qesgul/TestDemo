# -*- coding: utf-8 -*-
"""ApiResponse：对 Playwright APIResponse 的轻量包装（不复制 body）。

持有原始对象引用，status/ok/headers 直接代理；json()/text 转发到原始对象。
同时携带请求元信息（method/url/body）供 ApiAssertion 诊断捕获使用。
"""


class ApiResponse:
    def __init__(self, raw, *, elapsed_ms: int,
                 request_method: str = None,
                 request_url: str = None,
                 request_body=None):
        self._raw = raw
        self.elapsed_ms = elapsed_ms
        self.request_method = request_method
        self.request_url = request_url
        self.request_body = request_body

    @property
    def status(self) -> int:
        return self._raw.status

    @property
    def ok(self) -> bool:
        return self._raw.ok

    @property
    def headers(self) -> dict:
        return self._raw.headers

    def json(self):
        """解析响应 body 为 dict / list。"""
        return self._raw.json()

    @property
    def text(self) -> str:
        """响应 body 原文。"""
        return self._raw.text()
