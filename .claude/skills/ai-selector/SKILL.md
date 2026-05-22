---
name: ai-selector
description: >
  Use when generating or filling Playwright selectors/locators from test cases or
  element descriptions. Triggers on: "用AI获取selector"、"帮我找元素的selector"、
  "ai-selector"、"fill TODO_SELECTOR"、"自动生成定位器"、"selector_finder"。
  工作模式：Claude 自身读取页面快照（ARIA 树 + 截图），按内置 9 条规则生成并验证
  locator，写入 pages/elements/*.yaml。无需 API Key，无 LLM 调用代码。
---

# AI Selector Finder v2（Claude-Driven）

## 当前能力

| 阶段 | 状态 |
|------|------|
| yaml 复用：规范化匹配已有 key，verifier 确认 | ✅ |
| 快照抓取：ARIA 树（YAML）+ 截图 → 文件 | ✅ |
| Claude 分析快照 → 3 个候选 locator（9 条规则）| ✅ |
| 验证：verify_locator.py → JSON 结果 | ✅ |
| 自修复：失败时按错误类型重新分析，重试 1 次 | ✅ |
| 人工兜底：AI 全失败 → find_selectors.py | ✅ |
| 特殊场景：上传 / 动态文本 / 加载中 | ✅ |

**流水线**: `yaml 复用 → AI 分析（快照 + 规则）→ 验证 → 自修复 → 人工兜底`

## 前置条件

- 项目根目录已激活 Python 虚拟环境（`.venv/`）
- `playwright install chromium` 已完成
- 工作目录：项目根（`/d/code/TestDemo`）

---

## 工作流（严格按顺序执行）

### Step 1. 确认输入

收集以下信息（缺少任何一项则向用户提问）：

| 参数 | 说明 |
|------|------|
| `TARGET_URL` | 目标页面 URL（必须可访问，需已登录时先处理 cookie） |
| `INPUT` | 用例 markdown 文件路径，或手动列出的元素描述列表 |
| `OUTPUT_YAML` | 写入哪个 `pages/elements/*.yaml` |
| `ELEMENTS_DIR` | 现有 yaml 目录，默认 `pages/elements` |

如果用户提供了 `tests/data/xxx.md` 用例文件，提取步骤：

```python
import sys; sys.path.insert(0, ".")
from common.selector_finder.extractor import extract_steps_from_file
steps = extract_steps_from_file("tests/data/xxx.md")
for s in steps:
    print(s.step_index, s.element_desc, s.action)
```

---

### Step 2. yaml 复用检查

对**每个**待处理元素，先查已有 yaml：

```python
import sys; sys.path.insert(0, ".")
from common.selector_finder.yaml_reuse import find_existing
result = find_existing("<element_desc>", "pages/elements")
print(result)  # (LocatorSpec, action) 或 None
```

- **命中** → 直接用 `write_element.py` 写入 OUTPUT_YAML（key 已存在则跳过），标记 `source=yaml_reuse`
- **未命中** → 进入 Step 3

---

### Step 3. 抓页面快照

对每个未命中的元素，运行：

```bash
python scripts/capture_snapshot.py \
  --url <TARGET_URL> \
  --out .planning/snapshot/step_<N>/ \
  [--focus "<元素描述关键词，如 上传、加载>"]
```

然后用 Read 工具读取以下两个文件（**都要读**）：
- `.planning/snapshot/step_<N>/a11y.yaml` — ARIA 可访问性树
- `.planning/snapshot/step_<N>/screenshot.png` — 页面截图

---

### Step 4. 生成候选 locator（核心分析步骤）

读取快照后，综合 ARIA 树和截图，为目标元素生成 **3 个候选**。

#### 9 条规则（必须严格遵守，违反任何一条视为错误）

1. **优先级（必须按此顺序选择）**：
   `test_id > role+name > label > placeholder > text > css`

2. **禁止绝对路径 CSS/XPath**（如 `html > body > div:nth-child(3) > button`）

3. **禁止动态 ID 和 hash 类名**（如 `#btn-123456`、`.css-1x8dfjg`、`.sc-abcXYZ`）

4. **优先链式定位**：先定位父容器，再在容器内定位子元素
   - 用 `scope` 字段指定父容器 CSS
   - 示例：`{"type":"role","role":"button","name":"确定","scope":"[class*='Modal']"}`

5. **优先 filter() 思路**：如果角色/文本重复，用 `scope` 限定范围，不写复杂单层 CSS

6. **必须唯一匹配**，禁止依赖 `first()/last()/nth()`（除非 verify 验证后确认是唯一手段）

7. **getByRole 必须带 name**，优先 `exact: true`

8. **输出 3 个候选**，按规则 1 的优先级从高到低排列（候选1 最优）

9. **每个候选附 rationale**（选择原因，供自修复参考，写入时会自动去除）

#### 候选输出格式（必须用此结构，直接可粘贴给 verify_locator.py）

```json
[
  {
    "type": "role",
    "role": "button",
    "name": "提交",
    "exact": true,
    "rationale": "按钮有明确 name，role+name 语义最强，稳定性高"
  },
  {
    "type": "css",
    "selector": "#OperationForm-btnSubmit",
    "rationale": "稳定 ID，不含动态数字或 hash，次优"
  },
  {
    "type": "label",
    "label": "提交表单",
    "exact": false,
    "rationale": "aria-label 关联，备用兜底"
  }
]
```

---

### Step 5. 逐一验证候选

对 3 个候选中的**每一个**（按序从高优先级到低），运行：

```bash
python scripts/verify_locator.py \
  --url <TARGET_URL> \
  --spec '<单个候选 JSON，去掉 rationale>'
```

示例：
```bash
python scripts/verify_locator.py \
  --url https://your-app.com/page \
  --spec '{"type":"role","role":"button","name":"提交","exact":true}'
```

结果解析：
- `"unique": true` → ✅ 采用此 locator，进入 Step 7 写入
- `"unique": false, count > 1` → 不唯一，尝试下一个候选
- `"unique": false, count = 0` → 未找到，尝试下一个候选
- **全部候选都失败** → 进入 Step 6 自修复

---

### Step 6. 自修复（仅触发一次）

收集所有失败信息，按以下模板重新分析（重新读 a11y.yaml + screenshot.png）：

```
目标元素：<element_desc>
动作：<action>

上次 3 个候选全部 verify 失败：
  候选1 {"type": ...}: count=<N>, error="<msg>"
  候选2 {"type": ...}: count=<N>, error="<msg>"
  候选3 {"type": ...}: count=<N>, error="<msg>"

根据以下规则重新分析，给出新的 3 个候选（不得与上次重复）：

失败原因分析规则：
- count > 1 → 必须加 scope 父容器 CSS 缩小范围，或用 filter() 精细化匹配
- TimeoutError → 元素在弹窗/动态加载后出现，改选更稳定的祖先节点，或检查 scene_hooks
- count = 0（name 相关）→ 改 exact: false，或截取更短的文本子串
- not visible / count = 0（css）→ 检查是否被遮挡，考虑祖先节点
```

生成新候选后，再次执行 Step 5 验证。仍全部失败 → 进入 Step 8。

---

### Step 7. 写入 yaml

候选验证通过后，运行：

```bash
python scripts/write_element.py \
  --yaml <OUTPUT_YAML> \
  --key "<step_index>_<element_desc>" \
  --spec '<通过验证的候选 JSON（含或不含 rationale 均可，脚本自动去除）>' \
  [--action upload]
```

key 命名规则：`step{index}_{element_desc}`，与测试步骤对应。

标记此元素 `source=ai`，继续处理下一个元素（回到 Step 2）。

---

### Step 8. 人工兜底（AI 完全失败时）

对仍未解析的元素，告知用户：

```
以下元素 AI 无法自动定位，请运行 find_selectors.py 手动点选：

  [步骤 N] <element_desc>（action: <action>）

命令：
  python scripts/find_selectors.py \
    --url <TARGET_URL> \
    --input <INPUT_FILE> \
    --output <OUTPUT_YAML>
```

---

### Step 9. 汇总报告

```
[完成] AI Selector 生成报告
  yaml 复用：  N 个（直接复用，0 次快照）
  AI 生成：    N 个（其中自修复 N 个）
  待人工处理：  N 个

  输出文件：<OUTPUT_YAML>

未解析元素（需人工）：
  [步骤 N] <element_desc>
```

---

## 特殊场景处理

### 场景一：上传按钮

触发条件：元素描述含"上传"/"截图"/"图片"/"文件"/"upload"/"attach"

```bash
# --focus 上传 触发 upload_detect 场景钩子，探测 input[type=file]
python scripts/capture_snapshot.py --url <URL> --out .planning/snapshot/stepN/ --focus 上传

# write 时加 --action upload
python scripts/write_element.py --yaml <YAML> --key <KEY> \
  --spec '{"type":"css","selector":"input[type=\"file\"]"}' --action upload
```

优先 locator：`{"type":"css","selector":"#uploadWrapper input[type=\"file\"]"}`  
兜底：`{"type":"css","selector":"input[type=\"file\"]"}`

### 场景二：动态文本（数字/状态切换词）

⚠ **不稳定示例**：`{"type":"text","text":"6生成"}` — 数字会变

改用（按优先级）：
1. `test_id`
2. `css` 稳定 ID（如 `#OperationForm-btnSubmit`）
3. `role+name` 配合短且固定的子串（不含数字）

### 场景三：动态加载（SPA / 无限滚动）

```bash
# --focus 加载 触发 wait_network_idle 钩子
python scripts/capture_snapshot.py --url <URL> --out .planning/snapshot/stepN/ --focus 加载
```

---

## 核心模块位置

| 模块 | 路径 |
|------|------|
| 快照抓取脚本 | `scripts/capture_snapshot.py` |
| 定位器验证脚本 | `scripts/verify_locator.py` |
| yaml 写入脚本 | `scripts/write_element.py` |
| 人工兜底入口 | `scripts/find_selectors.py` |
| yaml 复用逻辑 | `common/selector_finder/yaml_reuse.py` |
| 场景钩子 | `common/selector_finder/scene_hooks.py` |
| 唯一性验证 | `common/selector_finder/verifier.py` |
| 人工点选 | `common/selector_finder/human_picker.py` |
| 步骤提取 | `common/selector_finder/extractor.py` |

## 不做的事

- 不调用任何 LLM API（无 API Key，无 SDK 调用）
- 不修改 `pages/elements/*.yaml` 中已有的非 TODO 条目
- 不把 hash 类名（`.btn_a3f9c2`）写入 yaml
- 不把含数字的动态文本（"6生成"）作为主定位策略
- 不在脚本里写调度逻辑（调度在此 SKILL.md 中）
