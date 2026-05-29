# Claude 行为规范（TestDemo 项目）

本文件约束 Claude 在该项目中的**交互行为**，优先级高于默认系统行为。
所有测试代码约定以 `.cursor/rules/*.mdc` 为权威；本文件只规范 Claude 的操作方式。

---

## 最高优先级：改动确认机制（规则 5）

**所有涉及文件改动的操作，必须先输出方案，等用户明确确认后才执行。**

### 必须确认再执行的场景

- 新建文件（包括测试用例、Page Object、YAML、脚本）
- 修改现有文件（包括追加内容）
- 删除文件或清理临时文件
- 修改任何配置文件
- 运行会产生副作用的脚本（如数据采集、快照更新）

### 方案输出格式

```
【改动方案】
1. 文件 A：<改动内容概述>
2. 文件 B：<改动内容概述>
...
请确认后我再执行。
```

### 用户确认信号

以下回复视为确认，可以执行：
- "确认"、"好的"、"可以"、"执行"、"OK"、"yes"、"是"

收到确认前**绝不操作文件**，即使任务看起来简单明确。

---

## 数据采集确认机制（规则 1）

凡是需要「采集页面数据并将其保存为后续比对基准」的操作：

1. **先执行采集**，将结果完整打印到终端
2. **暂停写入文件**，输出如下提示：

```
【采集结果确认】
共采集到以下数据，请确认无误后我再写入 YAML：
  rank_3d   : 10 条 —— [法式复古客餐厅 | 109216 | 172-222元, ...]
  rank_su   : 10 条 —— [现代吧台 | 23043 | 182-438元, ...]
  ...
```

3. 用户确认后才调用 `save_snapshot_to_yaml` / 写文件

适用场景：
- `collect_inspiration_data.py` 等数据采集脚本
- 任何将动态列表写入 YAML `snapshots:` 键的操作
- 首次为某个功能建立快照基准

---

## Git 提交确认机制（规则 6）

**禁止在未经用户明确同意的情况下执行任何 `git commit`。**

### 必须等待明确指令才能执行的 git 操作

- `git commit`（任何形式，包括 `--amend`）
- `git push`
- `git rebase`
- `git merge`
- `git tag`

### 确认方式

需要用户**主动发出提交指令**，例如：
- "提交"、"commit"、"帮我提交"、"git commit"
- 或在任务完成后用户说 "提交一下" 等明确语句

**即使任务全部完成，也必须等用户主动要求后才能提交。**

### 禁止的行为

- 在执行计划（executing-plans / subagent）过程中自动提交
- 在完成文件改动后"顺手"提交
- 以"每个任务一个 commit"为由在未获许可时提交

---

## 改动前检查清单

执行任何代码改动时，自查以下事项：

- [ ] 是否已输出方案并等待确认？（规则 5）
- [ ] 若涉及数据采集，是否已先打印结果等待确认？（规则 1）
- [ ] 新增方法是否已列出所有调用路径并验证？（见 pageobject-conventions.mdc）
- [ ] 同类方法默认参数是否与已有方法保持一致？（见 pageobject-conventions.mdc）
- [ ] 动态列表断言是否使用了快照比对而非裸 len 判断？（见 test-suite-conventions.mdc）

---

## 文件归属说明

| 关注点 | 权威文件 |
|---|---|
| Claude 交互行为 | 本文件（`CLAUDE.md`） |
| Page Object / YAML 编写规范 | `.cursor/rules/pageobject-conventions.mdc` |
| 测试用例编写规范 | `.cursor/rules/test-suite-conventions.mdc` |
| 数据文件格式 | `.cursor/rules/test-data-conventions.mdc` |
| 会话复盘 / 清理机制 | `.claude/skills/session-recap/SKILL.md` |

---

## Skill 触发映射（优先级最高）

识别到以下任意触发词，**必须在执行任何操作前**先调用对应 `Skill`：

| 触发词（任意匹配一个即触发） | 必须先调用 |
|---|---|
| 总结改动 / 会话复盘 / session recap / 汇总今日改动 / 汇总改动 / 生成复盘报告 / 清理临时文件 / 清理废弃脚本 / clean artifacts / 这段时间的问题 / 改动总结 | `Skill("session-recap")` |
| 清理无用文件 / 清理项目 / clean-artifacts | `Skill("clean-artifacts")` |
| 把这份用例转成自动化 / 生成用例代码 / 根据 markdown 生成 / convert test cases / 转成自动化代码 | `Skill("case-to-code")` |
| 用AI获取selector / 帮我找元素的selector / fill TODO_SELECTOR / 自动生成定位器 / ai-selector / selector_finder / 生成元素定位 | `Skill("ai-selector")` |

规则：**识别到触发词 → 立即 `Skill(name)` → 再做其他任何事。即使只是想先问问题或采集信息也不例外。**
