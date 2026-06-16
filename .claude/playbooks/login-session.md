# 问题域：登录态与跨子域 session

## 知末网登录弹窗为扫码默认态，必须按顺序操作才渲染输入框
- **问题域**: 登录弹窗
- **症状**: 直接 `goto` 目标页后卡在登录弹窗；弹窗默认是扫码二维码态，找不到手机号 / 密码输入框，selector 抓取与后续交互全部失败。
- **根因**: 知末网各子站（www / su / sgt / 3d 等交互一致）登录弹窗默认渲染扫码态，账号密码输入框是**懒渲染**——必须按固定顺序点击切换，输入框才会出现。直接跳目标页不会自动带出可输入的登录表单。
- **解决方案**: **先登录、再 goto 目标页**，禁止先跳目标页再处理登录。统一复用项目登录方式（`pages/methods/login_page.py` 的 `login_with()` + `pages/elements/login_page_elements.yaml` 现成选择器），按以下顺序操作弹窗：
  1. 点「手机」tab
  2. 点「账号密码登录」
  3. 填手机号
  4. 填密码
  5. 提交
  6. 等登录弹窗消失（确认登录态生效）
  然后再 `goto` 目标页执行抓取 / 交互。
- **适用 agent**: selector-debug / gio-tracking
- **最近验证日期**: 2026-06-09

## CAS 多 service 回调：同一 TGT 一次覆盖所有 .znzmo.com 子域（B 方案）
- **问题域**: 跨子域session/CAS多service
- **症状**: Playwright `new_context()` ≈ 无痕模式，第三方 cookie 受限，CAS TGC 跨子域静默登录被拦截；各子域（su / 3d）单独出现登录弹窗，之前靠 `_ensure_su_login` UI 逐域登录，效率低且脆弱。
- **根因**: CAS SSO 跨子域静默登录靠读认证中心域的 TGC cookie，Playwright context 的第三方 cookie 限制（SameSite）使其失效。各子域须各自持有 CAS callback 派发的本地 session cookie。
- **解决方案**: `common/api/auth.py` 新增 `establish_subdomain_sessions(playwright, context, page, username, password)`：用同一账密拿新鲜 TGT，对 `_SUBDOMAIN_SERVICES` 列表中每个子域 POST TGT 换 ST → `page.goto(service?ticket=ST)` 执行 CAS callback → session cookie 落入同一 context cookie jar。`conftest.py` 在 `cas_login()` 之后调用，一次性覆盖 su / 3d，完全替代 `_ensure_su_login`。扩展新子域只需往 `_SUBDOMAIN_SERVICES` 列表追加 URL。
- **验证结论（2026-06-16）**: 知末 CAS 白名单放行 su / 3d service；三子域全覆盖后访问业务页登录框 count=0 visible=False。
- **适用 agent**: conftest / code-engineer（扩展子域时）
- **最近验证日期**: 2026-06-16

## 跨子域不共享 session（debug 工具侧仍适用，test suite 侧已由 B 方案根治）
- **问题域**: 跨子域session
- **症状**: 在 `www.znzmo.com` 登录拿到 cookie 后，套到 `su.znzmo.com` 等子站直接 goto，目标操作仍被判未登录 / 触发登录弹窗。
- **根因**: Playwright `new_context()` 第三方 cookie 受限，CAS TGC 跨域读取失败；各子域独立鉴权。
- **解决方案**:
  - **test suite 侧**：已由 `establish_subdomain_sessions`（B 方案，见上方条目）根治，conftest 启动时一次覆盖所有子域，无需额外处理。
  - **debug 工具侧（selector-debug / gio-tracking / capture_snapshot.py）**：这些工具创建独立 browser context，不共享 conftest 的 cookie。仍须在目标操作所在子域 **UI 登录**（同「登录弹窗顺序」流程）或用 `ensure_storage_state`（login_session.py）复用缓存态。
- **适用 agent**: selector-debug / gio-tracking
- **最近验证日期**: 2026-06-16

## 跨 TLD 站点（.znzmo.cn）用 storage_state 复用登录态，解决反复登录问题
- **问题域**: 跨TLD登录/storage_state复用
- **症状**: `ai.znzmo.cn` 等与 `znzmo.com` 不同 TLD 的站点，每次抓取都要重新登录。`common/api/auth.py` 的 CAS 登录仅针对 `.znzmo.com`，对 `.znzmo.cn` 完全无效。
- **根因**: 不同 TLD（`.com` vs `.cn`）cookie 天然隔离，无法跨用。项目 `capture_snapshot.py` 和 `pipeline.py` 原本都创建匿名 browser context，没有登录态复用机制。
- **解决方案**: 使用 `common/selector_finder/login_session.py` 的 `ensure_storage_state(url, user, pwd)` 一次登录、多次复用：
  1. 首次调用 → 自动 UI 登录 → 将 Playwright `storage_state`（含 cookies + localStorage）保存到 `.auth/<domain>_state.json`（已在 `.gitignore` 中排除）。
  2. 后续调用 → 检测缓存未过期（默认 12h）→ 直接返回路径，`browser.new_context(storage_state=path)` 免登录。
  3. 无凭据 → 返回 None → 降级为匿名 context（原有行为，不破坏兼容性）。
- **CLI 用法**:
  ```bash
  # capture_snapshot.py
  python scripts/capture_snapshot.py --url https://ai.znzmo.cn/... --login-user 手机号 --login-pwd 密码
  # 或用环境变量
  CAPTURE_LOGIN_USER=手机号 CAPTURE_LOGIN_PWD=密码 python scripts/capture_snapshot.py --url ...

  # find_selectors.py
  python scripts/find_selectors.py --url https://ai.znzmo.cn/... --input tests/data/case.md --output pages/elements/xxx.yaml --login-user 手机号 --login-pwd 密码
  ```
- **已验证登录流程（ai.znzmo.cn 2026-06-15）**:
  - 登录入口: `#loginsuccessnews`（点击）或 `.AIpublicHeader__loginWrapper__QSXAF`（force click）
  - 顺序: 手机 tab → 账号密码登录 / 密码登录 → `input[placeholder*="手机"]` 填号码 → `input[type="password"]` 填密码 → `[class*="login-btn"]` 提交
  - 登录态判定: `#loginsuccessnews` 不再可见
  - 弹窗清除: 登录后再 `reload_dismiss_popups()` 一次（约 1 次 reload 清空）
- **适用 agent**: selector-debug / gio-tracking
- **最近验证日期**: 2026-06-15

## 3d.znzmo.com LoginModal 延迟出现（conftest B 方案已根治；此条保留供 debug 工具参考）
- **问题域**: 3d子站session/LoginModal时序
- **状态**: **test suite 侧已由 conftest `establish_subdomain_sessions`（B 方案，2026-06-16）根治**——session 启动时对 3d 子域做 CAS callback，LoginModal 不再出现，`DownloadAbPage.goto()` 的 domcontentloaded hack 可保留（无害）但不再必需。
- **症状（debug 工具独立 context 仍可能遇到）**: `page.goto()` 导航到 3d.znzmo.com 后，按钮点击超时——Playwright 报 `LoginModal__loginModalContainer__cD5qO intercepts pointer events`。
- **根因**: 3d.znzmo.com 前端在未建立本地 session 时，约 2s 后延迟弹出 LoginModal 拦截所有点击。
- **解决方案（debug 工具 / 独立 context）**: 使用 `domcontentloaded` 导航后在 ~800ms 内完成点击（在 LoginModal 出现前）；或先对 3d 子域做一次 `establish_subdomain_sessions` 建立 session，之后正常点击。
  ```python
  # 临时绕过（timing hack，不推荐长期依赖）
  page.goto(url, wait_until="domcontentloaded")
  page.wait_for_timeout(800)
  page.locator(download_btn).click()
  ```
- **适用 agent**: selector-debug / code-engineer（独立 context 调试时）
- **最近验证日期**: 2026-06-16

## 非校验目标弹窗一律 reload 绕过，不死磕关闭按钮
- **问题域**: 弹窗处理
- **症状**: 抓取 / 调试过程中，页面弹出 `.ant-modal-wrap` 层叠弹窗（如促销弹窗、引导弹窗），阻塞点击导致 selector 抓取失败、登录入口点击超时。花大量时间在 DOM 里查找关闭按钮但命中不稳定（svg/div 混用，无唯一 selector）。
- **根因**: 弹窗 DOM 结构复杂，关闭按钮 selector 不稳定；但 reload 后弹窗清除，页面恢复正常。
- **解决方案**: 复用 `common/selector_finder/login_session.py` 的 `reload_dismiss_popups(page, max_reloads=3)`：
  - 检测 `.ant-modal-wrap, .ant-modal-mask` 是否可见
  - 可见则 `page.reload(wait_until="domcontentloaded")` + 等 2.5s
  - 最多 3 次，实测 2 次即清空 ai.znzmo.cn 的所有阻塞弹窗
  - **例外**：有明确「校验弹窗」的测试用例，不 reload，正常走断言流程
- **适用 agent**: selector-debug / gio-tracking
- **最近验证日期**: 2026-06-15

## 账号锁定：错密码多次提交触发知末风控锁号（正确密码也被拒）
- **问题域**: 账号锁定/登录风控
- **症状**: 登录账号用错误密码多次提交会触发知末账号锁定（约 15-30 分钟自动解锁）。**锁定期内即使用正确密码，su.znzmo.com 登录弹窗也一律提示「账号或密码错误」、LoginModal 不关闭**，极易被误判为密码错或脚本 bug，进而去钻 selector / 脚本兔子洞。
- **根因**: 知末风控锁号机制——错密码累计触发锁定后，锁定期对正确凭据也统一拒绝，与密码本身正确与否无关。
- **解决方案**:
  1. 登录失败**先核对 `tests/data/account_pool.yaml`** 的账号 / 密码（当前 nonvip `13140725123`、VIP `17768100279` 均为 `Qyff2011`），**禁止凭记忆 / 沿用旧密码**（本会话误用 `Qss123456` 即触发锁号）。
  2. 密码确认无误仍失败 → 判为锁定期，**停手等 15-30 分钟自动解锁，禁止反复试登录**（反复试会刷新 / 延长锁定计时）。
- **避坑**:
  - 别把「账号锁」误判为 selector / 脚本 bug 去钻兔子洞。
  - 别删 `.auth/*storage_state*.json` 登录缓存（与锁号无关，本会话误删过；该文件不被 `logged_in_context` fixture 使用）。
- **适用 agent**: selector-debug / gio-tracking / code-engineer
- **最近验证日期**: 2026-06-16
