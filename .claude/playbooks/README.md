# 踩坑库（Playbooks）

本目录只存**已解决、可复用的自动化调试解法**。使用时先看下面路由表，命中后读对应文件的「速查」，仍卡住再读「详情」。

## 快速路由

| 看到的现象 / 关键词 | 先读文件 | 适用 agent |
|---|---|---|
| selector 多命中、点错元素、hash class、active 判断、`is_visible(timeout=...)` | `selector.md` | `selector-debug` / `code-engineer` |
| 登录弹窗、扫码默认态、跨子域 session、`.znzmo.cn` 登录、账号锁定、URL 没跳到目标页 | `browser-conventions.md（登录与会话章节）` | `selector-debug` / `gio-tracking` / `code-engineer` |
| GIO 事件找不到、body 明文搜不到、埋点断言怎么写 | `gio-tracking.md` | `gio-tracking` |
| 下一条用例开下载弹窗超时、fixture teardown 后状态残留 | `selector.md（弹窗状态残留章节）` | `code-engineer` / `test-runner` |
| Windows 终端中文乱码、`UnicodeEncodeError`、`¥` 打印失败 | `windows-env.md` | 所有 agent |

## 使用规则

1. **consult（查解法）**：调试前按关键词读对应文件，只执行命中的「直接做」。
2. **capture（回写）**：新坑解决后按 `_template.md` 追加，先写速查，详情从简。
3. **不进库**：研发缺陷不进踩坑库。核心交互未实现、接口报错、埋点 handler 未挂、页面白屏等，按规则8输出【缺陷反馈】/【阻断提示】。

## 条目规范

每个条目必须包含：

| 字段 | 说明 |
|---|---|
| 看到这个现象 | 可检索的报错、UI 现象、count 数、事件缺失 |
| 直接做 | 可复制执行的步骤、工具或代码策略 |
| 不要做 | 已验证会浪费时间或误判的做法 |
| 适用场景 | 适用页面、工具或 agent |
| 最近验证日期 | `YYYY-MM-DD` |

## 维护边界

- 由 `troubleshooter` 或主 agent 统一维护。
- 本目录是知识文档，不碰生产代码、不执行 git 操作。
- 目标是“快速命中”，不是写完整复盘；长背景放到「详情」，不要压住速查结论。
