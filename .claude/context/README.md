# 项目代码上下文（Context）

> 维护者：coder / code-reviewer 在涉及相关模块时读取并更新。
> 定位：改代码时需要的项目上下文，不是产品知识（→ knowledge/），不是流程（→ skills/）。
> 更新原则：代码变动导致上下文过时时，更新对应卡片；每条尽量精简，关键信息给路径+行号。

## 索引

| 上下文卡 | 内容 | 适用场景 |
|---|---|---|
| [fe-popup-priority.md](fe-popup-priority.md) | AI绘图弹窗优先级链（20个Wrapper完整优先级表） | 新增/修改弹窗、排查弹窗顺序 |
| [fe-common-utils.md](fe-common-utils.md) | 公共hooks + 工具函数关键词映射 | 写新功能前查是否已有封装好的工具 |
| [fe-state-management.md](fe-state-management.md) | Redux/Zustand双状态体系注入指南 | 涉及全局状态读取/新增 |
| [fe-routing-map.md](fe-routing-map.md) | zhimo_web2.0完整路由映射 | 新增/修改页面路由、排查路由冲突 |

## 使用约定

1. **coder agent 前置**：涉及前端改动时，先读相关 context 卡，避免重复造轮子
2. **code-reviewer 校验**：评审时检查是否正确引用了已有公共方法/路由/状态
3. **更新时机**：代码变动导致上下文过时时，更新对应卡片
4. **读取方式**：按需读取，不必全读；关键词匹配后用 Read 工具加载对应文件的指定行

## 与 knowledge/ 的区别

| 维度 | knowledge/ | context/ |
|---|---|---|
| 内容 | 产品规则/术语/业务逻辑 | 项目代码结构/公共方法/技术约定 |
| 粒度 | 短条目（≤3行） | 长文档/映射表/代码示例 |
| 消费者 | test-design（生成用例） | coder / code-reviewer（写/审代码） |
| 更新频率 | 低（产品规则稳定） | 中（代码变动时更新） |
