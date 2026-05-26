---
name: ai-selector
description: >
  Use when generating or filling Playwright selectors/locators from test cases or
  element descriptions. Triggers on: "用AI获取selector"、"帮我找元素的selector"、
  "ai-selector"、"fill TODO_SELECTOR"、"自动生成定位器"、"selector_finder"。
  工作模式：Claude 自身读取页面快照（ARIA 树 + 截图），按内置 9 条规则**批量**生成并
  验证 locator，写入 pages/elements/*.yaml。一次循环搞定多个元素，无需 API Key。
---

# AI Selector Finder v3（Claude-Driven · 批量贪心）

## 当前能力

| 阶段 | 状态 |
|------|------|
| 批量 yaml 复用：一次扫描所有 yaml，多元素并行匹配 | ✅ |
| 快照抓取：ARIA 树（YAML）+ 截图 → 文件 | ✅ |
| Claude 批量分析：一份快照 → 多元素 × 3 候选 | ✅ |
| 批量验证：verify_locator.py --specs-json，一次浏览器跑 N 个 spec | ✅ |
| 同批自修复：失败元素一起重试 1 次（复用快照 + 错误信息塞 prompt） | ✅ |
| 跨状态贪心：找不到的元素留到下一轮主循环 | ✅ |
| 死锁保护：连续 2 轮 pending 无消化 → 强制转人工 | ✅ |
| 人工兜底：仍未解析 → find_selectors.py | ✅ |
| 特殊场景：上传 / 动态文本 / 加载中 | ✅ |

**流水线**：`批量 yaml 复用 → 主循环(贪心批量 AI 分析 → 批量 verify → 同批自修复) → 人工兜底`

---

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

将得到一个 `pending` 待处理元素清单（含 step_index / element_desc / action）。

---

### Step 2. 批量 yaml 复用过滤

一次性查所有 pending 元素：

```python
import sys; sys.path.insert(0, ".")
from common.selector_finder.yaml_reuse import find_existing_batch

descs = [s.element_desc for s in steps]  # 或手动列出的 desc 列表
result = find_existing_batch(descs, "pages/elements")
# result: {desc: (LocatorSpec, action)}, 只含命中的
print(f"yaml 复用命中 {len(result)}/{len(descs)} 个")
```

对命中的元素：

```bash
# 构造批量写入 JSON
python -c "
import json
batch = [
    {'key': 'step1_点击家装', 'spec': {'type': 'role', 'role': 'button', 'name': '家装'}, 'action': None},
    # ... 命中的所有元素
]
print(json.dumps(batch, ensure_ascii=False))
" > .planning/snapshot/reuse_batch.json

python scripts/write_element.py --yaml <OUTPUT_YAML> --batch-json .planning/snapshot/reuse_batch.json
```

未命中的元素进入 `pending` 列表，进入 Step 3。

如果 `pending` 为空 → 跳到 Step 7（汇总）。

---

### Step 3. 主循环初始化

```python
pending: list = [...]           # 未命中 yaml 的元素清单（含 step_index, element_desc, action）
human_fallback_queue: list = [] # 最终转人工的元素
last_pending_size: int = -1     # 死锁检测
stagnant_rounds: int = 0        # 连续无消化的轮数
attempts: dict = {}             # desc → 尝试次数（>3 强制转人工）
loop_count: int = 0
```

---

### Step 4. 主循环（while pending 非空 and stagnant_rounds < 2）

#### 4a. 抓快照

```bash
python scripts/capture_snapshot.py \
  --url <TARGET_URL> \
  --out .planning/snapshot/loop_<N>/ \
  [--focus "<关键词，含上传/加载时>"]
```

用 Read 工具读取：
- `.planning/snapshot/loop_<N>/a11y.yaml`
- `.planning/snapshot/loop_<N>/screenshot.png`

#### 4b. Claude 批量分析

把以下信息综合分析，**一次性**给所有 pending 元素生成候选：

```
[场景上下文]
URL: <TARGET_URL>
本轮已成功定位的元素（避免重复推荐）:
  - step1_xxx: {role: button, name: "确定"}
  ...

[待处理元素清单]
  1. step2_点击家装 (action=click)
  2. step4_标准模式知点数字 (action=expect_text)
  3. step5_切换到思考模式按钮 (action=click)
  ...

[9 条规则]
（见下方"9 条规则"小节）

[期望输出格式 — YAML，所有 pending 元素都要返回]
elements:
  step2_点击家装:
    found: true
    candidates:
      - {type: role, role: button, name: 家装, exact: true, rationale: "..."}
      - {type: css, selector: "#category-home", rationale: "..."}
      - {type: text, text: 家装, exact: true, rationale: "..."}
  step5_切换到思考模式按钮:
    found: false
    reason: "需先点击家装才会显示模式切换控件"
```

**Claude（你）阅读 a11y.yaml + screenshot.png 后，直接生成上述 YAML 结构作为对话回复。**

#### 4c. 批量 verify

把 found=true 的元素整理为 `to_verify.json`：

```python
import json
to_verify = []
for key, body in llm_output["elements"].items():
    if body.get("found") and body.get("candidates"):
        # 取候选 1（最优先）
        spec = {k: v for k, v in body["candidates"][0].items() if k != "rationale"}
        to_verify.append({"key": key, "spec": spec})
Path(".planning/snapshot/loop_N/to_verify.json").write_text(
    json.dumps(to_verify, ensure_ascii=False))
```

```bash
python scripts/verify_locator.py \
  --url <TARGET_URL> \
  --specs-json .planning/snapshot/loop_<N>/to_verify.json
```

输出 `[{key, unique, count, visible, error}, ...]`。

#### 4d. 收集结果

```python
verify_results = json.loads(stdout)
success: list = []        # (key, spec) — 候选1 unique 即成功
retry_bucket: list = []   # (key, body) — 候选1 失败，进同批重试
for row in verify_results:
    if row["unique"]:
        success.append((row["key"], to_verify_map[row["key"]]))
    else:
        retry_bucket.append((row["key"], llm_output["elements"][row["key"]]))
```

#### 4e. 同批自修复（仅 retry_bucket 非空时）

Claude 阅读相同的 a11y.yaml + screenshot.png，对 retry_bucket 元素重新分析：

```
[上轮 verify 结果 — 失败元素]
step4_标准模式知点数字: count=3 (不唯一)
step6_xxx: TimeoutError 30000ms

对上轮失败的元素重新推荐（同份快照，不重抓），参考失败原因规则：
- count > 1 → 必须加 scope_css 父容器，缩小范围
- TimeoutError → 选更稳定的祖先节点，或检查是否被弹窗遮挡
- count = 0 (name not found) → 改 exact: false 或更短文本子串
- not visible → 检查是否被遮挡，改选可见祖先节点

[输出格式同 4b]
```

把新候选再次构造 `to_verify.json` 跑 verify_locator.py。

仍失败的元素 → 加入 `human_fallback_queue`，从 pending 移除。
重试成功的 → 加入 `success`。

#### 4f. 批量写入 yaml

```python
to_write = [
    {"key": k, "spec": {k2: v2 for k2, v2 in spec.items() if k2 != "rationale"},
     "action": original_action_for_key.get(k)}
    for k, spec in success
]
Path(".planning/snapshot/loop_N/to_write.json").write_text(
    json.dumps(to_write, ensure_ascii=False))
```

```bash
python scripts/write_element.py --yaml <OUTPUT_YAML> --batch-json .planning/snapshot/loop_<N>/to_write.json
```

#### 4g. 更新 pending + 死锁检测

```python
# 移除已成功 + 已转人工的
done_keys = {k for k, _ in success} | {k for k, _ in retry_failed}
pending = [p for p in pending if p.element_desc not in done_keys]

# 累加 attempts；超 3 次强制转人工
for p in pending:
    attempts[p.element_desc] = attempts.get(p.element_desc, 0) + 1
    if attempts[p.element_desc] > 3:
        human_fallback_queue.append(p)

pending = [p for p in pending if attempts[p.element_desc] <= 3]

# 死锁检测
if len(pending) == last_pending_size:
    stagnant_rounds += 1
else:
    stagnant_rounds = 0
last_pending_size = len(pending)
loop_count += 1
```

---

### Step 5. 主循环退出条件

- `pending` 空 → 全部解决，跳到 Step 7
- `stagnant_rounds >= 2` → 死锁，剩余 pending 全部加入 `human_fallback_queue`

---

### Step 6. 人工兜底

对 `human_fallback_queue` 元素，告知用户：

```
以下元素 AI 无法自动定位，请运行 find_selectors.py 手动点选：

  [步骤 N] <element_desc>（action: <action>，原因: <reason 或 'verify 反复失败'>）

命令：
  python scripts/find_selectors.py \
    --url <TARGET_URL> \
    --input <INPUT_FILE> \
    --output <OUTPUT_YAML>
```

---

### Step 7. 汇总报告

```
[完成] AI Selector 生成报告
  主循环轮次：  <loop_count> 轮
  yaml 复用：   <yaml_reuse_count> 个（0 次 LLM 调用）
  AI 一次命中： <ai_first_hit_count> 个
  AI 自修复后命中：<ai_self_heal_count> 个
  待人工处理：  <human_fallback_count> 个

  输出文件：<OUTPUT_YAML>

未解析元素（需人工）：
  [步骤 N] <element_desc>
```

---

## 9 条规则（必须严格遵守）

1. **优先级**：`test_id > role+name > label > placeholder > text > css`

2. **禁止绝对路径 CSS/XPath**（如 `html > body > div:nth-child(3) > button`）

3. **禁止动态 ID 和 hash 类名**（如 `#btn-123456`、`.css-1x8dfjg`、`.sc-abcXYZ`）

4. **优先链式定位**：父容器 + scope 缩小范围

5. **优先 filter() 思路**：用 scope 而非复杂单层 CSS

6. **必须唯一匹配**，禁止依赖 `first()/last()/nth()`

7. **getByRole 必须带 name**，优先 `exact: true`

8. **每个元素输出 3 个候选**，按规则 1 从高到低排列

9. **每个候选附 rationale**（自修复参考；写入时自动去除）

---

## LLM 输出 schema 约束

每轮主循环 Claude 必须返回 **完整覆盖所有 pending 元素** 的 YAML：

```yaml
elements:
  <key1>:
    found: true | false
    # 仅 found=true 时存在
    candidates:
      - {type, ...field..., rationale}
      - ...
      - ...
    # 仅 found=false 时存在
    reason: "<为什么找不到，比如'需先点击 X 才会显示'>"
  <key2>:
    found: ...
```

**降级处理**：如果 Claude 自己解析输出时发现格式错误（YAML 解析异常），整批回退到单元素模式（每个 pending 元素单独走一次"读快照→生成 3 候选→verify"）。

---

## Token 防爆

- 软上限：每轮主循环最多 15 个 pending 元素塞 prompt
- 超过 15 个 → 按 step_index 取前 15 个，其余下轮处理（不计入 stagnant_rounds）
- 截图固定 1280×800 分辨率
- a11y 树由 capture_snapshot.py 自动裁剪

---

## 特殊场景处理

### 场景一：上传按钮

触发条件：元素描述含"上传"/"截图"/"图片"/"文件"/"upload"/"attach"

```bash
# --focus 上传 触发 upload_detect 场景钩子，探测 input[type=file]
python scripts/capture_snapshot.py --url <URL> --out .planning/snapshot/loop_N/ --focus 上传
```

LLM 候选中若含上传元素，写入时 batch-json 加 `"action": "upload"` 字段。

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
python scripts/capture_snapshot.py --url <URL> --out .planning/snapshot/loop_N/ --focus 加载
```

---

## 核心模块位置

| 模块 | 路径 |
|------|------|
| 快照抓取脚本 | `scripts/capture_snapshot.py` |
| 批量验证脚本 | `scripts/verify_locator.py` (`--specs-json`) |
| 批量写入脚本 | `scripts/write_element.py` (`--batch-json`) |
| 人工兜底入口 | `scripts/find_selectors.py` |
| 批量 yaml 复用 | `common/selector_finder/yaml_reuse.py` (`find_existing_batch`) |
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
- 不做运行时自愈（pytest 跑用例时动态修复 selector）
