---
name: session-recap
description: >
  会话复盘、改动汇总 skill。
  触发词：总结改动、会话复盘、session recap、汇总今日改动、汇总改动、
  生成复盘报告、这段时间的问题、改动总结。
---

# Session Recap — 会话复盘

> 清理交由 `clean-artifacts` skill / `cleanup` agent，本 skill 仅做会话复盘，不删任何文件。

## 触发词

以下任意词触发本 skill：
- "总结改动"、"会话复盘"、"session recap"
- "汇总今日改动"、"汇总改动"、"生成复盘报告"
- "这段时间的问题"、"改动总结"

---

## Step 1：确定时间范围

向用户询问（选其一）：

```
请选择复盘范围：
  A. 今天的全部改动（git log --since="today"）
  B. 最近 N 次提交（输入 N）
  C. 两个 commit hash / tag 之间
  D. 某个会话节点（粘贴关键消息或时间戳）
  E. 全部未提交改动（git diff / git status）
```

等用户回复后继续。

---

## Step 2：采集改动清单

```bash
# 获取指定范围内的改动文件列表
git log --oneline <范围>
git diff --stat <范围>
git diff --name-only <范围>
```

按以下类别分组输出：

| 类别 | 文件模式 | 说明 |
|---|---|---|
| 测试用例 | `tests/cases/test_*.py` | 用例新增/修改 |
| Page Object | `pages/methods/*_page.py` | PO 方法改动 |
| 元素定位 | `pages/elements/*.yaml` | selector 更新 |
| 数据文件 | `tests/data/*.yaml` | 测试数据/快照 |
| 公共工具 | `common/*.py` | 工具类改动 |
| 脚本 | `scripts/*.py` | 辅助脚本 |
| 规则/配置 | `AGENTS.md` / `.claude/rules/*.mdc` | 规范更新 |
| 其他 | 剩余文件 | — |

---

## Step 3：问题汇总报告

按"问题 → 根因 → 修复 → 遗漏点"格式输出，模板：

```
## 会话复盘报告（{日期范围}）

### 本次主要改动

| 序号 | 改动文件 | 改动类型 | 简述 |
|---|---|---|---|
| 1 | ... | 新增/修改/删除 | ... |

### 发现的问题与修复

#### 问题 1：{问题标题}
- **现象**：...
- **根因**：...
- **修复**：...
- **未能第一时间发现的原因**：...

#### 问题 2：...

### 应吸取的规范教训

- ...

### 本次未完成 / 遗留事项

- [ ] ...
```

---

## Step 4：文件合规校验

对改动范围内的所有文件执行以下检查：

### 4a. 语法验证
```bash
python -m py_compile <改动的 .py 文件>
```

### 4b. 用例可收集验证
```bash
pytest --collect-only tests/cases/<改动的 test_*.py> -q
```

### 4c. 快照数据校验

对每个含 `snapshots:` 键的 YAML 文件：
- 检查每个数据键的条目数是否合理（通常 ≥ 5 条）
- 检查条目格式是否包含多字段（含 ` | ` 分隔符）
- 输出异常项让用户决定是否重新采集

---

## Step 6：汇总输出

### 6a. 可复用知识候选

复盘结束前，识别本次是否产生可跨项目复用的内容：业务规则、接口契约、测试数据构造规则、常见缺陷、自动化踩坑、评审模式或发布事故教训。若有，追加“知识候选”小节，每项包含：

- 建议类型：`business-rule` / `contract` / `test-heuristic` / `case` / `test-data` / `review-pattern` / `incident` / `playbook`
- 一句话结论、适用范围、触发词
- 证据来源和置信度：`confirmed` / `inferred` / `proposed`
- 是否需要人工核验、是否可能与现有卡重复

候选项交给 `$test-knowledge-curator` 处理。默认只输出建议，不直接写入或升级中心知识库；中心库固定为 `D:\code\test-knowledge-base`，正式卡必须通过其校验和来源核验。

```
【复盘报告已生成】

改动文件：N 个
  - 测试用例：N 个
  - Page Object：N 个
  - 数据文件：N 个
  - 其他：N 个

问题复盘：N 个问题
  - 当时未立即发现：N 个
  - 用户指出后修复：N 个

文件校验：
  - 语法通过：N/N
  - 用例可收集：N/N
  - 快照数据异常：N 个（见上方详情）
```

---

## 注意事项

- **不修改任何业务代码**，只做检查与报告
- **本 skill 不删除任何文件**，清理需求请转 `clean-artifacts` skill / `cleanup` agent
- 若 git 历史或文件状态无法读取，提示用户手动提供范围
- 报告中的"未第一时间发现"是为了改进流程，不是指责，表述保持客观

---

## 快速示例

```
用户：总结今天的改动
Codex：
  Step 1 → 确认范围：今天 git log
  Step 2 → 列出改动文件
  Step 3 → 输出问题报告
  Step 4 → 运行语法校验 + 快照校验
  Step 6 → 汇总输出
```
