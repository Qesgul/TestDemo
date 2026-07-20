# 登录与会话复用

## 目标

模型在 selector 抓取、UI 自动化生成和调试功能时，必须先按目标 URL 获取登录态。不要先登录 A 域名再跳 B 域名，也不要把 `.znzmo.com` 的 cookie 套到 `ai.znzmo.cn`。

## 规则

1. 先识别目标 URL 的 auth profile：
   - 素材业务：`znzmo.com` 及其子域，scope 为 `znzmo_com`。
   - AI 绘图：`ai.znzmo.cn`，scope 为 `ai_znzmo_cn`。
2. 缓存文件按 `env + auth_scope + account_hash` 隔离，默认在 `.auth/`。
3. 复用缓存前必须打开目标 URL 验活；验活失败才允许 UI 登录一次。
4. UI 登录失败后停止并上报，不要重复试密码，避免触发账号锁定。
5. 账号只从 `tests/data/account_pool.yaml`、CLI 参数或环境变量读取。

## 使用方式

- 调试/selector 脚本：调用 `common.selector_finder.login_session.ensure_storage_state(url, user, pwd)`。
- 素材业务测试：使用 `logged_in_page`。
- AI 绘图测试：使用 `ai_draw_page`，它会创建独立的 `ai.znzmo.cn` context。
- 验证路由：运行 `python scripts/verify_auth_profiles.py`。
- 需要真实预热登录态时：运行 `python scripts/verify_auth_profiles.py --login --headless`。

## 不要做

- 不要假设 `.com` 和 `.cn` 共享 session。
- 不要复用非目标域 storage_state。
- 不要用 `api.znzmo.com` 的通用接口推断 `ai.znzmo.cn` 页面已登录。
- 不要在业务用例里重复写登录流程。
