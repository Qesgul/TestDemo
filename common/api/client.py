# -*- coding: utf-8 -*-
"""ApiClient：中等封装，base_url 拼接 + 默认 header/超时 + 耗时记录。

调用方写 path 与 payload；底层走 Playwright APIRequestContext.fetch。
支持 requests 风格 json=（自动映射为 Playwright fetch 的 data=，dict 被 JSON 序列化）。
"""
from time import perf_counter

from common.api.config import api_base_url, api_default_headers, api_timeout_ms
from common.api.response import ApiResponse


class ApiClient:
    def __init__(self, request_context, *,
                 base_url: str = None,
                 default_headers: dict = None,
                 timeout_ms: int = None):
        self._rc = request_context
        self._base = (base_url if base_url is not None else api_base_url()).rstrip("/")
        self._headers = {**api_default_headers(), **(default_headers or {})}
        self._timeout = timeout_ms if timeout_ms is not None else api_timeout_ms()

    def _full_url(self, path: str) -> str:
        if str(path).startswith("http"):
            return path
        return self._base + "/" + str(path).lstrip("/")

    def _send(self, method: str, path: str, *, headers: dict = None, **kw) -> ApiResponse:
        url = self._full_url(path)
        merged = {**self._headers, **(headers or {})}
        # requests 风格 json= → Playwright fetch 的 data=（dict 自动 JSON 序列化）
        if "json" in kw:
            kw["data"] = kw.pop("json")
        body = kw.get("data")
        t0 = perf_counter()
        raw = self._rc.fetch(url, method=method, headers=merged, timeout=self._timeout, **kw)
        elapsed_ms = max(0, int((perf_counter() - t0) * 1000))
        return ApiResponse(raw, elapsed_ms=elapsed_ms,
                           request_method=method, request_url=url, request_body=body)

    def get(self, path: str, **kw) -> ApiResponse:
        """HTTP GET。常用 params=，headers= 覆盖默认。"""
        return self._send("GET", path, **kw)

    def post(self, path: str, **kw) -> ApiResponse:
        """HTTP POST。支持 json={...}（自动序列化）或 data=（原始）。"""
        return self._send("POST", path, **kw)

    def put(self, path: str, **kw) -> ApiResponse:
        """HTTP PUT。"""
        return self._send("PUT", path, **kw)

    def delete(self, path: str, **kw) -> ApiResponse:
        """HTTP DELETE。"""
        return self._send("DELETE", path, **kw)
