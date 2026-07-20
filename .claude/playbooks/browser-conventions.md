# 浏览器操作与调试约定

## 一句话原则

启动浏览器做元素抓取、页面调试、交互验证时，统一用 Playwright 驱动；调试前先登录、先复用登录态，不要临时凭感觉处理。

## 工具约定

- **一律使用 Playwright**（`sync_playwright` / `capture_snapshot.py` / 自定义调试脚本）驱动，支持 headed 或 headless 模式。
- **禁止调用** `mcp__Claude_in_Chrome__*` 系列工具（Chrome 扩展连接不稳定，已弃用）。
- 需要用户可见的调试场景，使用 `headless=False` 启动有界面浏览器。
- `ai-selector` skill 及所有 selector 抓取流程均遵循此约定。

## 调试登录约定（必须先登录再跳转）

- **凭据必查账号池，禁止凭记忆**：需要登录账号时，统一从 `tests/data/account_pool.yaml` 取账号/密码，**禁止凭记忆 / 沿用旧密码**；登录失败先核对账号池凭据，确认无误仍失败即判为账号锁定期（错密码多次会锁号约 15-30 分钟），**停手等解锁、禁止反复试登录**（详见 上方「登录与会话规则·必守规则」第 4 条）。
- 调试场景若**提供了账号**或**需要登录态**，统一调用项目已有登录方式（`pages/methods/login_page.py` 的 `login_with()` / `login_page_elements.yaml` 现成选择器），**先完成登录，再 `goto` 目标页**，禁止直接跳目标页后卡在登录弹框。
- **知末网登录弹窗（www / su / sgt / 3d 等各子站交互一致）为扫码默认态**，需按顺序操作输入框才会渲染：点「手机」tab → 点「账号密码登录」→ 填手机号 → 填密码 → 提交 → 等登录弹窗消失。
- **跨子域不假设共享 session**：`www.znzmo.com` 的 cookie/CAS session 不一定通过 `su.znzmo.com` 等子站鉴权；目标操作所在子域可能独立鉴权，优先用 UI 登录验证而非套用 cookie。

## 登录态复用约定（三条红线，防止反复登录）

> 细则见 [login-session.md](login-session.md)。调试/selector 场景统一用目标 URL 调 `ensure_storage_state(url, user, pwd)`，由 auth profile 决定素材业务或 AI 绘图登录态。

1. **抓取 / 调试前优先复用 storage_state**：提供了账号凭据时，调用 `common/selector_finder/login_session.py` 的 `ensure_storage_state(url, user, pwd)` 获取缓存的登录态 JSON 路径，再 `browser.new_context(storage_state=path)` 启动——**不每次重新走 UI 登录流程**。`capture_snapshot.py` 和 `find_selectors.py` 已内置 `--login-user/--login-pwd` 参数（也可通过 `CAPTURE_LOGIN_USER/PWD` 环境变量传入）。

2. **非校验目标的弹窗一律 reload 绕过**：遇到 `.ant-modal-wrap / .ant-modal-mask` 阻塞交互时，调用 `reload_dismiss_popups(page)` 循环 reload（最多 3 次）直到弹窗消失——**禁止花时间猎取关闭按钮 selector**。例外：用例明确要校验某弹窗的，正常走断言，不 reload。

3. **跨 TLD（.cn vs .com）不假设共享 session**：`ai.znzmo.cn` 等与 `znzmo.com` 不同 TLD 的站点，`common/api/auth.py` 的 CAS 登录完全无效；须在目标 TLD 各自做 UI 登录，再用 storage_state 复用。

> 已验证解法与 ai.znzmo.cn 登录选择器详见 上方「登录与会话规则·常见场景怎么做」表格。

## 调试经验教训

- **selector 唯一性必须用官方工具验证**：用 `scripts/verify_locator.py --specs-json` 或 `common/selector_finder/verifier.build_locator`，判定标准 `count==1`，禁止用宽松的 `count>0`（会漏掉同名 class 的多命中，如本次 `promo_package_option` count=3）。
- **同名 hash class 无法区分时**：用标准 CSS 结构定位（`父容器 > 子:first-child`），属标准 CSS 伪类，非 Playwright `.first()`，符合 ai-selector 规则 6。（详见 [selector.md](selector.md)）
- **Windows 终端中文输出走文件**：含中文 / `¥` 的内容不在终端 `print`（GBK 报错），改为写 UTF-8 文件再用 Read 读出。（详见 [windows-env.md](windows-env.md)）
- **禁止 JS 移除遮挡元素**：类似 `_JS_REMOVE_MASK` 这类通过 JavaScript 移除遮罩/弹窗的操作，**必须避免使用**，除非实在无法通过正常交互绕过才考虑。原因：JS 移除元素会破坏页面状态导致后续操作异常；遮罩/弹窗的出现本身可能是业务逻辑（如"不支持该场景"），移除后会掩盖真实问题；移除后不会自动恢复，影响后续测试。正确做法：先判断遮罩是否为预期状态，通过 Playwright 原生交互绕过（如点击空白区域关闭弹窗、使用 `force=True` 绕过遮挡），只有在确认是页面 bug 且无法绕过时才考虑 JS 移除。
- **DOM 元素存在不代表可用**：获取模型列表等下拉选项时，需要检查按钮是否 disabled，不能仅凭 DOM 中有元素就认为可交互。JS 查询可能读到 CSS 隐藏的残留元素。
- **Playwright 点击不等于生效**：切换模型/场景后必须验证操作结果（如检查当前模型名称），不能假设点击就一定生效。批量执行时时序问题可能导致点击无效。
- **优化等待时间要谨慎**：不能一刀切去掉所有硬等待，部分场景切换需要一定时间才能生效。去掉等待会导致状态未更新就继续执行，造成大量场景被跳过。

## 不要做

- 不用 `mcp__Claude_in_Chrome__*` 系列工具。
- 不凭记忆写账号密码。
- 不反复试密码触发账号锁定。
- 不假设不同子域 / TLD 共享 session。
- 不用 JS 移除遮挡元素（除非确认是页面 bug 且无法绕过）。
- 不用 `count>0` 判断 selector 唯一性。
- 不假设点击一定生效，必须验证操作结果。

---

# 登录与会话规则

## 一句话原则

需要登录态时，先用项目统一登录 / 会话能力；不要临时凭感觉处理登录弹窗、cookie 或账号。

## 必守规则

1. **账号只从账号池取**：需要账号时读取 `tests/data/account_pool.yaml`，禁止凭记忆写账号 / 密码。
2. **自动化用例不重复登录**：业务用例需要登录态时优先用 `logged_in_page`，不要在用例里重复实现登录流程。
3. **独立调试才缓存登录态**：selector 抓取、截图、埋点探针等独立浏览器场景，使用 `ensure_storage_state(url, user, pwd)`。
4. **登录失败先防锁号**：账号池凭据确认无误仍失败，按账号锁定处理，停手等 15-30 分钟，不要反复试密码。

## 常见场景怎么做

| 场景 | 做法 |
|---|---|
| 自动化用例需要登录 | 用 `logged_in_page` fixture |
| 纯接口 / UI+API 需要登录态 | 按场景用 `api_client` / `logged_in_api_client` |
| selector-debug / capture_snapshot / find_selectors 需要登录 | 用 `ensure_storage_state(url, user, pwd)` 后 `browser.new_context(storage_state=path)` |
| `.znzmo.com` 子域登录态 | 依赖现有 `establish_subdomain_sessions` 覆盖 su / 3d 等子域 |
| `.znzmo.cn` 站点 | 单独 UI 登录，并用 storage_state 缓存；不要套 `.znzmo.com` cookie |
| 登录弹窗默认扫码态 | 手机 tab -> 账号密码登录 -> 手机号 -> 密码 -> 提交 -> 等弹窗消失 |
| 非校验目标弹窗挡住点击 | 用 `reload_dismiss_popups(page, max_reloads=3)` |
| 登录失败 | 先查 `tests/data/account_pool.yaml`；确认无误仍失败则等锁定解除 |
| PageObject `goto()` 后找不到元素 | 先检查 URL 是否到目标页，再排查 selector |

## 不要做

- 不凭记忆写账号密码。
- 不在业务用例里重复写登录流程。
- 不假设 `.znzmo.com` 与 `.znzmo.cn` 共享 session。
- 不假设 `www.znzmo.com` 的登录态自动覆盖所有子域调试 context。
- 不反复试密码，避免触发或延长账号锁定。
- 不把登录失败直接判成 selector 问题。
- 不为关闭非目标弹窗花大量时间找不稳定 selector。

## 工具速记

| 工具 / fixture | 用途 |
|---|---|
| `logged_in_page` | UI 用例复用登录态 |
| `api_client` | 纯接口测试，按需带 cookie，不启动浏览器 |
| `logged_in_api_client` | UI+API 混合用例，复用浏览器登录 session |
| `ensure_storage_state(url, user, pwd)` | 独立调试浏览器复用登录态 |
| `establish_subdomain_sessions(...)` | test suite 侧覆盖 `.znzmo.com` 子域 session |
| `reload_dismiss_popups(page, max_reloads=3)` | 非目标弹窗 reload 绕过 |

## 最近验证

- 登录弹窗顺序：2026-06-09
- `.znzmo.com` 子域 session：2026-06-16
- `.znzmo.cn` storage_state：2026-06-15
- PageObject `goto()` URL 验证：2026-07-07
- 账号锁定处理：2026-06-16
