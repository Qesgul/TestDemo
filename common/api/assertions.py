# -*- coding: utf-8 -*-
"""ApiAssertion：响应断言，复用 CheckpointReporter 汇总 + API 版诊断捕获。

失败时把请求/响应元信息写入 diagnostic_reports/<test>_api_<ts>.json，
遵守现有 DiagnosticAssertion.enabled / .diagnostic_dir 开关（--no-diagnostics 仍生效）。
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Optional

from common.assertions import CheckpointReporter, DiagnosticAssertion, _safe_repr


class ApiAssertion(CheckpointReporter):
    """API 响应断言：status_ok / status_is / json_path / json_contains。

    用法（pytest 用例内）：
        def test_xxx(self, api_client, api_assert):
            resp = api_client.get("/api/something")
            api_assert.status_ok(resp, name="接口可用")
            api_assert.json_path(resp, "code", 0, name="业务码为0")
    """

    def __init__(self, test_name: Optional[str] = None):
        super().__init__(test_name)

    # ── 内部工具 ──

    def _dig(self, obj: Any, path: str) -> Any:
        """按点路径深挖对象；list 用整数索引（"data.0.name"）。"""
        cur = obj
        for part in str(path).split("."):
            if isinstance(cur, list):
                cur = cur[int(part)]
            else:
                cur = cur[part]
        return cur

    def _capture(self, resp, assertion_name: str, err: Exception) -> None:
        """失败时把请求 + 响应元信息写入诊断文件。"""
        if not DiagnosticAssertion.enabled:
            return
        try:
            diag_dir = DiagnosticAssertion.diagnostic_dir
            os.makedirs(diag_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            fpath = os.path.join(diag_dir, f"{self.test_name}_api_{ts}.json")
            try:
                body = resp.text
            except Exception:
                body = None
            payload = {
                "assertion": assertion_name,
                "error": str(err),
                "request": {
                    "method": getattr(resp, "request_method", None),
                    "url": getattr(resp, "request_url", None),
                    "body": _safe_repr(getattr(resp, "request_body", None), 500),
                },
                "response": {
                    "status": getattr(resp, "status", None),
                    "headers": dict(getattr(resp, "headers", {}) or {}),
                    "body": body[:2000] if isinstance(body, str) else body,
                    "elapsed_ms": getattr(resp, "elapsed_ms", None),
                },
            }
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 诊断写入失败绝不影响测试主流程

    # ── 响应断言 ──

    def status_ok(self, resp, *, name: Optional[str] = None):
        """断言响应状态码为 2xx。"""
        start = time.perf_counter()
        try:
            assert 200 <= resp.status < 300, f"状态码 {resp.status} 非 2xx"
            self._record_checkpoint(name, "2xx", resp.status, "PASS", start, None, "status_ok")
        except Exception as e:
            self._record_checkpoint(name, "2xx", getattr(resp, "status", "?"),
                                    "FAIL", start, str(e), "status_ok")
            self._capture(resp, "status_ok", e)
            raise

    def status_is(self, resp, code: int, *, name: Optional[str] = None):
        """断言响应状态码精确等于 code。"""
        start = time.perf_counter()
        try:
            assert resp.status == code, f"期望状态码 {code}, 实际 {resp.status}"
            self._record_checkpoint(name, code, resp.status, "PASS", start, None, "status_is")
        except Exception as e:
            self._record_checkpoint(name, code, getattr(resp, "status", "?"),
                                    "FAIL", start, str(e), "status_is")
            self._capture(resp, "status_is", e)
            raise

    def json_path(self, resp, path: str, expected: Any, *, name: Optional[str] = None):
        """断言 json body 中按点路径取到的值等于 expected（支持 list 整数索引）。

        示例：
            api_assert.json_path(resp, "data.0.group_name", "默认分组", name="首个分组名")
        """
        start = time.perf_counter()
        try:
            actual = self._dig(resp.json(), path)
            assert actual == expected, f"{path}: 期望 {expected!r}, 实际 {actual!r}"
            self._record_checkpoint(name, expected, actual, "PASS", start, None, "json_path")
        except Exception as e:
            self._record_checkpoint(name, expected, "<取值失败>",
                                    "FAIL", start, str(e), "json_path")
            self._capture(resp, "json_path", e)
            raise

    def json_contains(self, resp, path: str, member: Any, *, name: Optional[str] = None):
        """断言 json body 中按点路径取到的容器包含 member。"""
        start = time.perf_counter()
        try:
            container = self._dig(resp.json(), path)
            assert member in container, f"{path}: 期望包含 {member!r}"
            self._record_checkpoint(name, f"包含 {_safe_repr(member, 40)}", container,
                                    "PASS", start, None, "json_contains")
        except Exception as e:
            self._record_checkpoint(name, f"包含 {_safe_repr(member, 40)}", "<取值失败>",
                                    "FAIL", start, str(e), "json_contains")
            self._capture(resp, "json_contains", e)
            raise
