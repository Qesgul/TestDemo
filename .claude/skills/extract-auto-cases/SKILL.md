---
name: extract-auto-cases
description: Use when the user provides existing test cases (Markdown table OR Excel/.xlsx) plus optional requirement docs and asks to extract / distill automation test cases. Filters which cases are automatable, rewrites them into a FIXED 12-column automation-case template (atomic steps + assertion points + test data + requirement traceability), uses the requirement doc to fill coverage gaps, and writes the result back in the SAME format as the input (md→md table, xlsx→xlsx). Output feeds directly into the case-to-code skill. Triggers on phrases like "提取自动化测试用例"、"从用例提取自动化"、"筛选可自动化用例"、"把测试用例转成自动化用例"、"根据需求和用例生成自动化用例"、"extract automation cases".
---

# 测试用例 + 需求 → 自动化测试用例（提取/改写层）

把外部「全量测试用例（含手工用例）」结合「需求文档」，**筛选**出可自动化的部分并**改写**成一套
*固定列结构*的「自动化测试用例」。本层是**设计层**，产物是代码生成（`case-to-code` skill）的上游输入，
本 skill 不直接出 Playwright/pytest 代码。

> 本 skill 是 **Codex 专用**，与 Cursor IDE 的 `.claude/rules/*.mdc` 无关。
> 与 `case-to-code` 的关系：本 skill 产出「自动化测试用例（md/excel）」→ 交给 `case-to-code` 生成可运行代码。
> 自动化可行性分级词汇（`auto/network/env/manual`）**与 `case-to-code` 保持一致**，确保两段流水线无缝衔接。

## 触发场景

用户给出**已有测试用例**（md 表格或 Excel）+（可选）需求文档，要求提取/筛选/改写为自动化用例。典型语句：
- "把 `xxx.md` / `xxx.xlsx` 里能自动化的用例提取出来"
- "结合这份需求，从用例里筛选自动化用例"
- "根据需求和用例生成自动化测试用例"

## 输入

| 项 | 说明 | 必填 |
|---|---|---|
| 测试用例 | Markdown 表格 **或** Excel(.xlsx) | ✅ |
| 需求文档 | PRD / 需求说明（任意格式：md/word/pdf/纯文本） | 可选（强烈建议，用于查漏补全） |

- 输入用例常见列：`用例编号 / 标题 / 优先级 / 前置条件 / 测试步骤 / 预期结果`（列名可有出入，按语义对齐）。
- **先确定输入格式并记录** `输入格式 = md / xlsx`，输出格式必须与之一致（见「格式保持」）。

## 核心产物：固定「自动化测试用例」模板

无论输入长什么样，统一映射到下面这套**固定 12 列**。md 输出 = markdown 表格表头；xlsx 输出 = 首行表头。

| # | 列名 | 含义 | 来源 |
|---|------|------|------|
| 1 | 自动化用例编号 | `AUTO-{模块}-{3位序号}`，如 `AUTO-LOGIN-001` | 从源用例派生 |
| 2 | 源用例编号 | 输入用例原始编号 | 正向追溯，便于回查 |
| 3 | 用例标题 | 动宾短语，≤ 30 字 | 输入 / 精炼 |
| 4 | 所属模块 | 功能模块 / 页面 | 输入 / 需求 |
| 5 | 优先级 | P0 / P1 / P2 / P3 | 输入（缺失则按需求重要度估并备注） |
| 6 | 自动化分级 | `auto` / `network` / `env` / `manual` | 见「分级规则」 |
| 7 | 前置条件 | 含登录态、数据准备 | 输入 + 需求补全 |
| 8 | 测试数据 | 输入参数 / 账号 / 期望文案 | 输入 + 需求补全 |
| 9 | 测试步骤 | **原子化**，每步一个动作，`1. 2. 3.` 编号 | 改写 |
| 10 | 预期结果(校验点) | 每步对应**可断言**校验点，与步骤一一对应 | 改写 + 需求查漏 |
| 11 | 需求追溯 | REQ-ID / PRD 章节号 | 需求文档（无则留 `-`） |
| 12 | 备注 | manual 原因 / 依赖桩 / 待澄清 / 需求补全 标注 | 标注 |

## 分级规则（沿用 case-to-code 词汇）

| 分级 | 触发条件 | 改写策略 |
|------|------|------|
| `auto` | 纯 UI 操作 + UI 可断言（可见、文案、选中态） | 原子化步骤 + 明确校验点 |
| `network` | 涉及"调用接口/工作流 ID""接口失败""白屏""loading""调用记录" | 同上，备注「需 route 拦截/接口桩」 |
| `env` | 涉及"网络中断""弱网""CDN""离线" | 同上，备注「需 offline/限速」 |
| `manual` | "目视判断""对比基准截图""大模型识别""两端对比""【待澄清】" | **保留用例**，步骤照写，校验点写"人工目视"，备注写明为何不可自动化 |

## 需求查漏补全（规则：补全 > 照抄）

有需求文档时，除改写已有用例外，还须**反向核对覆盖**：

1. 把需求拆成可验证的功能点 / 边界 / 接口要求 / 埋点要求清单。
2. 逐条比对现有用例是否覆盖；**需求要求但用例漏掉**的自动化校验点（典型：埋点上报、接口异常、边界值、必填校验），
   **补成新的自动化用例行**，`源用例编号` 填 `-（需求补全）`，`备注` 标 `需求补全`。
3. 补全的用例同样要落「自动化分级」，不能默认 `auto`。

## 格式保持（强约束）

| 输入 | 输出文件 | 输出形态 |
|---|---|---|
| `xxx.md`（markdown 表格） | `xxx_auto.md` | markdown 表格，固定 12 列 |
| `xxx.xlsx`（Excel） | `xxx_auto.xlsx` | Excel，首行固定 12 列表头，一行一用例 |

- **输入什么格式就按什么格式输出**，不擅自换格式。
- 输出文件名 = `{原文件名去扩展名}_auto.{原扩展名}`，与输入同目录。
- 若输入是「贴在对话里的表格」而非文件，则按用户输入推断格式；默认 md，并提示可指定。

### Excel 读写实现

- **读** `.xlsx`：用 `openpyxl`（已在依赖中）按行读首个工作表；
  必要时调 `anthropic-skills:xlsx` skill 处理复杂样式/多 sheet。
- **写** `.xlsx`：用 `openpyxl` 新建工作簿，首行写 12 列表头，逐行写用例，列宽自适应即可。
- 多行文本（步骤/预期）单元格内用换行（`\n`）保留编号列表。

最小读写骨架（仅示意，按需调整）：

```python
# 读
from openpyxl import load_workbook
wb = load_workbook("xxx.xlsx", data_only=True)
ws = wb.active
rows = [[c.value for c in row] for row in ws.iter_rows()]

# 写
from openpyxl import Workbook
out = Workbook(); s = out.active
s.append(["自动化用例编号","源用例编号","用例标题","所属模块","优先级",
          "自动化分级","前置条件","测试数据","测试步骤","预期结果(校验点)","需求追溯","备注"])
for case in cases:
    s.append([...])
out.save("xxx_auto.xlsx")
```

## 工作流（5 步）

### Step 1. 识别输入格式
- 判定 `输入格式 = md / xlsx`（文件扩展名或对话内容）。
- md → `Read` 文件；xlsx → openpyxl 读取首个 sheet。

### Step 2. 解析
- 抽取输入用例表（列名按语义对齐到固定模板）；同义/重复块去重。
- 有需求文档 → 拆功能点 / 边界 / 接口 / 埋点要求清单备用。

### Step 3. 逐条筛选 + 分级
- 每条用例打 `auto/network/env/manual` 标签 + 一句理由。
- `manual` 保留不丢。

### Step 4. 改写为固定模板 + 需求查漏
- 步骤原子化（一步一动作）；每步补**可断言**校验点；补前置/测试数据/需求追溯。
- 执行「需求查漏补全」：漏掉的需求校验点补成新行，标 `需求补全`。

### Step 5. 同格式输出 + 提取报告
- md→`xxx_auto.md`（表格）；xlsx→`xxx_auto.xlsx`（同表头）。
- 终端打印**提取报告**：
  - 输入文件 + 输入格式
  - 输出文件路径
  - 分级统计：`auto / network / env / manual` 各几条
  - 需求补全条数 + 补了哪些校验点
  - 待澄清清单（`【待澄清】` / 缺优先级 / 缺需求追溯）
- 收尾建议：可把 `xxx_auto.md` 交给 `case-to-code` 生成可运行代码。

## 红线（与 AGENTS.md 规则 8 / gio 指南一致）

- **不伪造断言**：`manual` 用例只写"人工目视"，绝不用 `assert_true(True)` 之类糊弄。
- **不掩盖缺陷**：改写中发现疑似功能缺陷（区别于用例本身写得含糊），按 `AGENTS.md 规则 8` 格式即时反馈；
  严重缺陷先阻断、等指示，不默默 skip。
- **不丢用例**：不可自动化的用例标 `manual` 保留，不静默删除。
- **不换格式**：输入什么格式输出什么格式，不擅自转。
- **需求缺失要标注**：没有需求文档时，「需求追溯」列填 `-`，并在提取报告里提示"未做需求查漏"。

## 改动确认（AGENTS.md 规则 5）

写出 `xxx_auto.md` / `xxx_auto.xlsx` 属于「新建文件」，**必须先输出【改动方案】等用户确认**后再写。
采集/解析阶段可先把分级与查漏结果打印到终端供确认。

## 不做的事（边界）

- 不直接生成 Playwright/pytest 代码（那是 `case-to-code` 的职责）。
- 不改写输入原文件（只产出 `_auto` 新文件）。
- 不在缺需求时臆造需求追溯 ID。
