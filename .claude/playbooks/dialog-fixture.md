# 问题域：弹窗状态与 fixture teardown 时序

## 级联弹窗服务端状态残留：上条用例未显式关弹窗就 close，阻塞下一条开弹窗
- **问题域**: 弹窗服务端状态/fixtureteardown
- **症状**: function-scoped `new_page` 用例打开 `DownloadConfirmModal` 后，若未显式关闭就 `page.close()`，服务端「下载流程进行中」状态会短暂残留，阻塞**紧接着启动的下一条用例** → 下一条 `wait_for_download_dialog` 超时（`TimeoutError: 8000ms exceeded`，等 `[role="dialog"]:has([class^="DownloadConfirmModal__"])`）。典型受害者是序列中第二条开弹窗用例。
- **根因**: fixture teardown 遵循 LIFO——模块级 autouse fixture 比 test 参数先 setup、故后 teardown；`logged_in_page`（负责关 page）先于模块级 `_auto_close_download_dialog` teardown 执行。对 `new_page` 而言 teardown 时 page 已关，autouse 兜底关不到 → 服务端缺少显式取消信号，「下载流程进行中」状态未被清除。
- **解决方案**: 在 `logged_in_page` fixture teardown 内、`page.close()` **之前**显式 click 弹窗关闭按钮（`[class^="DownloadConfirmModal__btnClose__"]`）发送取消信号清掉服务端状态（`conftest.py` 约 L173-186）。注意判断可见性用无参 `is_visible()`（立即型 API，见 `selector.md` 同类条目）。
- **验证**: VIP 账号两轮多组连续开弹窗用例，级联超时零复发（本会话 test-runner 验证）。
- **适用 agent**: code-engineer / selector-debug
- **最近验证日期**: 2026-06-16
