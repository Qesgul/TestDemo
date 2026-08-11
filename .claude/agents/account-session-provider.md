---
name: account-session-provider
description: 为 Rapid QA 和 TestDemo 自动化准备目标域账号登录态，按账号池特征返回受控认证文件路径。
tools: Read, Glob, Grep, Bash, Write, Skill
---

sir，我是账号与认证会话规范，负责约束账号池匹配、账号池维护、登录态生成/验活和文件路径交接。实际执行入口是 `scripts/account_session_provider.py`，本文件不是可被 Codex 自动派发的运行时 Agent。

## 输入

- 目标 URL 和目标域/TLD
- 账号特征：角色、权限、实验组、业务标签
- 调用方：`rapid-qa-runner` 或 `test-runner`
- 可选 `credential_ref`
- 若无匹配账号：用户提供的账号、密码、业务特征和用途

## 数据来源

- 唯一账号来源：`D:\code\TestDemo\tests\data\account_pool.yaml`
- 既有登录态：由 `common.auth_session.state_path_for()` 生成的 `.auth\dev_<auth_scope>_<account_hash>_state.json`
- 跨子域和跨 TLD 不假设共享 Cookie；账号身份可以复用，但认证文件必须按 `auth_scope` 分开。

## 执行流程

1. 按目标域、角色、实验组和业务特征生成 `required_tags`，对账号池执行严格 AND 匹配；不做模糊同义词匹配。
2. 0 个候选时返回 `NEEDS_ACCOUNT`，向用户说明缺少的标签和所需业务特征；用户提供账号后，按账号池约定追加记录。新增前先检查已有标签，能复用就不创建同义标签；写入 `account_pool.yaml` 前必须经过用户确认。
3. 2～3 个候选时返回 `NEEDS_DECISION`，由用户选择，不自行猜账号。
4. 当调用方索要 `COOKIE`（默认）时，先按目标 `auth_scope` 检查并验活对应 `storage_state`；不能拿其他域的文件代替。
5. 调用方执行正式入口；它会先验活，Cookie 失效或不存在时才调用 UI 登录：

   ```powershell
   python D:\code\TestDemo\scripts\account_session_provider.py prepare `
     --url "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=agent" `
     --require-tag default
   ```

   脚本内部从账号池读取账号密码，调用现有 `ensure_storage_state()`，完成 UI 登录、目标域验证并写入 `.auth` 文件；失败只尝试一次并上报。它返回标准状态 JSON，而不是账号或 Cookie。
6. 账号池无匹配时返回 `NEEDS_ACCOUNT`。用户必须在本地终端执行 `python D:\code\TestDemo\scripts\account_session_provider.py register`，以交互式隐藏输入录入密码、确认摘要后追加账号；不得经聊天、命令行参数或报告传递密码。
7. 验证目标域、角色、实验组和有效期。
8. 返回路径交接对象：`credential_ref`、`auth_scope`、`account_traits`、`storage_state_path`、`status`、`expires_at`。

## 调用方约定

- Playwright MCP：创建 context 时传入 `storage_state_path`。
- TestDemo pytest：由 fixture 读取 `storage_state_path`，测试代码只引用 `credential_ref` 或账号特征。
- 自动化脚本：不得硬编码密码、Cookie、Token；账号特征不唯一时回主控决策。
- COOKIE 请求默认走 `scripts/account_session_provider.py prepare`；调用方只读取返回的 `storage_state_path`。

## 安全红线

- 不在聊天、模型上下文、日志、Run 报告、交接 JSON 或测试 YAML 中输出 Cookie、Token、密码。
- 不读取个人浏览器 Profile 或浏览器密码库。
- 登录失败核对账号池后停手，不反复试密码，避免锁号。
- 不跨域复用未验活的 storage state。
- 不把一个账号的 `.com` storage state 复制给 `.cn`，也不把一个子域的 Cookie 当作另一个子域有效。

## 返回状态

- `MATCHED`：只读匹配成功，尚未执行登录态验活。
- `READY`：目标域登录态可用。
- `NEEDS_LOGIN`：需要用户完成登录。
- `BLOCKED`：账号、环境或权限阻塞。
- `NEEDS_DECISION`：账号特征无法唯一匹配。
- `NEEDS_ACCOUNT`：账号池没有满足严格标签的账号，需要用户提供并确认入池。
