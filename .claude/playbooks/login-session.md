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

## 跨子域不共享 session，优先 UI 登录验证而非套 cookie
- **问题域**: 跨子域session
- **症状**: 在 `www.znzmo.com` 登录拿到 cookie 后，套到 `su.znzmo.com` 等子站直接 goto，目标操作仍被判未登录 / 触发登录弹窗。
- **根因**: 不能假设各子域共享 session——`www.znzmo.com` 的 cookie / CAS session 不一定通过 `su.znzmo.com` 等子站鉴权；目标操作所在子域可能**独立鉴权**。
- **解决方案**: **不套用跨子域 cookie 假设共享**。在目标操作所在子域，直接用项目 **UI 登录**（同上「登录弹窗顺序」流程）完成鉴权再操作，用 UI 登录验证而非复制 cookie；确需带 cookie 时也要在目标子域实测登录态是否生效。
- **适用 agent**: selector-debug / gio-tracking
- **最近验证日期**: 2026-06-09

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
