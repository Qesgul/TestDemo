# AI Selector Finder v2 — Prompt-Driven 设计文档

**日期**: 2026-05-22  
**状态**: 已批准  
**范围**: `common/selector_finder/` + `scripts/` + `.claude/skills/ai-selector/SKILL.md`

---

## 1. 背景与目标

### 背景

v1 已实现：yaml 复用检查 → 人工点选兜底（`human_picker`）。人工点选的问题：
- 每个新页面都要重新点一遍，无法批量
- 含动态文本元素容易选错

### 目标

引入 AI（Claude Code 自身）作为"智能定位器"，在 yaml 复用未命中后、人工兜底之前，插入一层：
**Claude 自己读快照（a11y 树 + 截图）→ 按规则生成候选 locator → 脚本验证 → 写入 yaml**。

### 硬约束

- **不在项目中配置任何 API key 或模型相关内容**
- **不在脚本中做任何 LLM 调用**
- **调度逻辑全部在 SKILL.md 提示词中**，脚本只做原子操作

---

## 2. 整体架构

```
用户触发 ai-selector skill
        │
        ▼
[Claude Code 按 SKILL.md 执行]
        │
        ├─① 解析输入（用例 md / TODO_SELECTOR / URL）
        │
        ├─② yaml 复用检查（python 内联调用 yaml_reuse）
        │    命中 → 直接落 yaml，跳转 ⑤
        │
        ├─③ 未命中元素，逐个处理：
        │    a. Bash: capture_snapshot.py → .planning/snapshot/<N>/
        │    b. Read: a11y.json + screenshot.png
        │    c. Claude 自己分析（按 SKILL.md 内嵌的 9 条规则）→ 3 个候选
        │    d. Bash: verify_locator.py → JSON 结果
        │    e. unique=true → Bash: write_element.py → yaml
        │    f. 失败 → 按 SKILL.md 自修复 prompt 重新分析 → 重试 1 次
        │
        ├─④ 仍失败 → 告知用户运行 find_selectors.py 人工兜底
        │
        └─⑤ 汇总报告（复用 N 个 / AI N 个 / 失败 N 个）
```

### 与 v1 的关系

```
v1:  yaml_reuse → human_picker
v2:  yaml_reuse → [AI + 自修复] → human_picker（兜底不变）
```

---

## 3. 文件清单

| 文件 | 状态 | 大小 | 职责 |
|------|------|------|------|
| `.claude/skills/ai-selector/SKILL.md` | **重写** | ~250 行 | 调度提示词 + 9 条规则 + 自修复模板 |
| `scripts/capture_snapshot.py` | **新增** | ~80 行 | 抓 a11y 树 + 截图，落文件 |
| `scripts/verify_locator.py` | **新增** | ~60 行 | 验证 locator 唯一性，JSON stdout 输出 |
| `scripts/write_element.py` | **新增** | ~40 行 | 单元素追加写入 yaml（不覆盖已有 key） |
| `scripts/find_selectors.py` | **保留** | — | 人工兜底入口（已有） |
| `common/selector_finder/yaml_reuse.py` | **保留** | — | yaml 复用逻辑（已有） |
| `common/selector_finder/scene_hooks.py` | **保留** | — | 场景钩子（已有） |
| `common/selector_finder/verifier.py` | **保留** | — | 唯一性验证（已有） |
| `common/selector_finder/human_picker.py` | **保留** | — | 人工点选（已有） |

**不新增任何 LLM 调用代码**，不修改 `requirements.txt`。

---

## 4. 脚本接口

### 4.1 `scripts/capture_snapshot.py`

**职责**：启动 Playwright 浏览器，抓取页面 a11y 树和截图，输出到文件。

```
python scripts/capture_snapshot.py \
    --url <URL>                  # 必填
    --out <目录>                 # 默认 .planning/snapshot/
    [--focus "<关键词>"]         # 触发对应 scene_hooks（如"上传"触发 upload_detect）
    [--browser chromium]         # chromium / firefox / webkit
```

**输出文件**：
```
<out>/
  a11y.json       # 裁剪后的 a11y 树，仅保留 role/name/value/checked/expanded
  screenshot.png  # 全屏截图（1280x800）
  meta.json       # { url, timestamp, viewport, focus_kw }
```

**a11y 裁剪规则**（写在脚本里）：
- 去掉 `hidden: true`、`name` 为空且无子节点的节点
- 保留字段：`role`, `name`, `value`, `checked`, `expanded`, `level`
- 最大深度限制：10 层

### 4.2 `scripts/verify_locator.py`

**职责**：对一个 locator spec，验证它在目标页面是否唯一匹配且可见。

```
python scripts/verify_locator.py \
    --url <URL>                  # 必填
    --spec '<JSON>'              # 必填，locator spec，同 YAML 格式 JSON 化
    [--browser chromium]
```

**stdout 输出**（JSON，供 Claude 解析）：
```json
{"unique": true, "count": 1, "visible": true, "error": null}
{"unique": false, "count": 3, "visible": true, "error": null}
{"unique": false, "count": 0, "visible": false, "error": "TimeoutError"}
```

**spec 格式示例**：
```json
{"type": "role", "role": "button", "name": "提交", "exact": true}
{"type": "css", "selector": "#OperationForm-btnSubmit"}
{"type": "text", "text": "家装", "exact": true}
```

### 4.3 `scripts/write_element.py`

**职责**：将单个元素追加写入 yaml（不覆盖已有 key）。

```
python scripts/write_element.py \
    --yaml <yaml 文件路径>       # 必填
    --key <元素 key>             # 必填，如 "step3_提交按钮"
    --spec '<JSON>'              # 必填，同 verify 的 spec
    [--action upload]            # 可选，写入 action: upload
    [--force]                    # 覆盖已有 key（默认拒绝）
```

---

## 5. SKILL.md 关键内容设计

### 5.1 触发条件

```
phrases: 用AI获取selector / 帮我找元素 / ai-selector / fill TODO_SELECTOR
         / 自动生成定位器 / selector_finder
```

### 5.2 执行流程（提示词骨架）

SKILL.md 包含以下章节（这是 Claude 自己的操作手册）：

1. **确认输入** — URL + 输入文件/TODO list + 输出 yaml 路径
2. **yaml 复用检查** — 调用 Python 代码内联测试
3. **抓快照** — `capture_snapshot.py` 命令模板
4. **生成候选 locator** — 9 条规则（见下节），输出结构化 JSON
5. **验证** — `verify_locator.py` 命令模板 + 结果解析
6. **自修复** — 失败时的分析模板（见下节）
7. **写入 yaml** — `write_element.py` 命令模板
8. **汇报** — 复用 N / AI N / 失败 N / TODO 列表

### 5.3 9 条 Locator 生成规则（内嵌 SKILL.md）

```
1. 优先级（必须严格按序）：
   test_id > role+name > label > placeholder > text > css

2. 禁止绝对路径 CSS（如 html > body > div:nth-child(3)）

3. 禁止动态 ID 和 hash 类名（如 .css-1x8dfjg, #btn-123456）

4. 优先链式定位：先定位父容器，再定位子元素
   示例：[container] >> [target]，或 scope 字段限定

5. 优先 filter()，而非复杂单一选择器

6. 必须唯一匹配，禁止 first()/last()/nth()（除非万不得已）

7. getByRole 必须同时指定 name，尽量 exact: true

8. 每次输出 3 个候选，按优先级 1→3 排序

9. 每个候选附 rationale（说明选择原因）
```

**输出格式**（Claude 生成时必须用此结构，直接粘贴给 verify 脚本）：

```json
[
  {"type": "role", "role": "button", "name": "提交", "exact": true,
   "rationale": "按钮有明确 name，语义最强"},
  {"type": "css", "selector": "#OperationForm-btnSubmit",
   "rationale": "稳定 ID，不含动态部分"},
  {"type": "label", "label": "提交表单", "exact": false,
   "rationale": "aria-label 关联，次选"}
]
```

### 5.4 自修复 Prompt 模板（内嵌 SKILL.md）

当 verify 失败时，Claude 按此模板重新分析：

```
上次候选 <spec> 验证失败：
  count=<N>, visible=<bool>, error=<msg>

分析规则：
- count > 1 → 加 scope_css 限定父容器，或用 filter() 精细化
- TimeoutError → 元素可能在弹窗/动态加载后出现，选更稳定的祖先节点
- count = 0 → name 文本不精确，改 exact: false 或更短子串
- not visible → 检查是否被弹窗遮挡，先用 popup_clear 钩子

重新读 a11y.json，给出新的 3 个候选（不能与上次候选重复）。
```

### 5.5 特殊场景规则（内嵌 SKILL.md）

| 场景关键词 | 处理方式 |
|------------|----------|
| 上传 / 截图 / 图片 / 文件 | 捕获时加 `--focus 上传`，优先找 `input[type=file]`，write 时加 `--action upload` |
| 动态数字（"6生成"、"剩余 N 个"） | ⚠ 标注，不用 text 匹配，改用父容器 css 或 test_id |
| 加载中 / 动态内容 | 加 `--focus 加载`，capture 前额外等待 networkidle |

---

## 6. 数据流（完整）

```
tests/data/my_cases.md
        │
        ▼ extractor.parse() (已有)
[ExtractedStep list]
        │
        ├─ for each step:
        │
        ├─ yaml_reuse.find_existing(desc, elements_dir)
        │     ├─ 命中 → source="yaml_reuse" → write_element.py
        │     └─ 未命中 ↓
        │
        ├─ capture_snapshot.py --url X --out .planning/snapshot/stepN/
        │
        ├─ [Claude Read a11y.json + screenshot.png]
        │
        ├─ [Claude 按 9 条规则生成 candidates JSON]
        │
        ├─ for candidate in candidates:
        │     verify_locator.py --url X --spec candidate
        │       unique=true → write_element.py → source="ai"
        │       unique=false → 继续下个候选
        │
        ├─ 全部失败 → 自修复 prompt → 重试 1 次
        │
        └─ 仍失败 → 标记 missing → 用户手动 find_selectors.py
```

---

## 7. 边界与约束

### 不做

- 不在任何脚本中调用 LLM API
- 不在项目中存储 API key 或模型配置
- 不修改 `BasePage`、`verifier.py`、`human_picker.py`、`extractor.py`
- 不修改 `requirements.txt`（3 个新脚本只用 Playwright + PyYAML，已有依赖）
- 不修改现有 yaml 中已有 key（只追加）

### 必须

- `capture_snapshot.py` 复用 `scene_hooks.apply_hooks()`（弹窗清除等）
- `verify_locator.py` 复用 `verifier.is_unique()`
- `write_element.py` 不覆盖已有 key（除非 `--force`）
- SKILL.md 中的 9 条规则、自修复 prompt 必须明确、可执行（无歧义）

---

## 8. 验证场景

实施完成后，手动跑以下 4 个场景确认：

| 场景 | 期望 |
|------|------|
| 1. 已有 yaml 的元素 | yaml_reuse 命中，0 次快照 |
| 2. 新页面元素（无 yaml） | AI 一次生成，verify 通过，source=ai |
| 3. 含动态文本的元素 | AI 第一轮失败（text 策略），自修复后改用 css/role，通过 |
| 4. 所有策略失败 | 输出 missing 列表，提示运行 find_selectors.py |

---

## 9. Token 预算参考

| 内容 | 估算 |
|------|------|
| a11y 树（裁剪后）| ~2–3K tokens |
| 截图（1280×800 PNG） | ~1–2K tokens |
| SKILL.md 中的规则 + 上下文 | ~600 tokens |
| 输出（3 个候选 + rationale）| ~400 tokens |
| **单元素总计** | **~4–6K tokens** |
| 含自修复重试 | **~8–10K tokens** |
| 10 元素用例（20% 自修复率） | **~65K tokens** |
