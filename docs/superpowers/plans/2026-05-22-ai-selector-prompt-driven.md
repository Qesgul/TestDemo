# AI Selector Finder v2 (Prompt-Driven) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 3 个原子工具脚本（capture_snapshot / verify_locator / write_element）并重写 SKILL.md，让 Claude Code 自身作为 AI 分析器，取代项目代码中的 LLM 调用。

**Architecture:** 脚本只做原子操作（抓快照 / 验证 locator / 写 yaml），不含调度逻辑。SKILL.md 是 Claude 的操作手册，包含完整的工作流、9 条 locator 规则和自修复 prompt 模板。现有 yaml_reuse / scene_hooks / verifier / human_picker 保持不变。

**Tech Stack:** Python 3.11+, Playwright sync API (已有), PyYAML (已有). 零新依赖。

---

## 文件结构

| 文件 | 状态 | 职责 |
|------|------|------|
| `scripts/capture_snapshot.py` | **新建** | 无头浏览器抓 a11y 树 + 截图，输出到目录 |
| `scripts/verify_locator.py` | **新建** | 验证 locator spec 唯一性，stdout JSON |
| `scripts/write_element.py` | **新建** | 追加单个元素到 yaml，拒绝覆盖已有 key |
| `.claude/skills/ai-selector/SKILL.md` | **重写** | Claude 操作手册：工作流 + 9 条规则 + 自修复模板 |
| `common/selector_finder/yaml_reuse.py` | **不改** | 复用 `_yaml_dict_to_spec` 和 `find_existing` |
| `common/selector_finder/verifier.py` | **不改** | 复用 `build_locator` 和 `is_unique` |
| `common/selector_finder/scene_hooks.py` | **不改** | 复用 `apply_hooks` |

---

## Task 1: `scripts/capture_snapshot.py`

**Files:**
- Create: `scripts/capture_snapshot.py`

> 抓取目标页面的 a11y 树（裁剪后）和截图，落到指定目录。供 Claude 用 Read 工具读取分析。

- [ ] **Step 1: 新建文件，写完整实现**

```python
#!/usr/bin/env python
"""
Capture page a11y tree + screenshot for Claude-driven selector analysis.

Usage:
    python scripts/capture_snapshot.py \\
        --url https://example.com \\
        --out .planning/snapshot/ \\
        [--focus "上传"]          # keyword → triggers scene_hooks
        [--browser chromium]

Outputs (in <out>/):
    a11y.json      pruned accessibility tree
    screenshot.png 1280x800 full-page screenshot
    meta.json      { url, timestamp, viewport, focus_kw }
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from common.selector_finder.models import ExtractedStep
from common.selector_finder.scene_hooks import apply_hooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger(__name__)


def _prune(node: dict, depth: int = 0, max_depth: int = 10) -> dict | None:
    """Remove hidden/nameless-leaf nodes; keep only test-useful fields."""
    if depth > max_depth or node.get("hidden"):
        return None

    children = [
        c for child in (node.get("children") or [])
        if (c := _prune(child, depth + 1, max_depth)) is not None
    ]

    name = (node.get("name") or "").strip()
    if not name and not children:
        return None  # nameless leaf → drop

    out: dict = {"role": node.get("role", "")}
    if name:
        out["name"] = name
    for field in ("value", "checked", "expanded", "level"):
        if node.get(field) is not None:
            out[field] = node[field]
    if children:
        out["children"] = children
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture page snapshot for AI selector")
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--out", default=".planning/snapshot", help="Output directory")
    parser.add_argument("--focus", default="", help="Keyword for scene hooks (e.g. '上传')")
    parser.add_argument("--browser", default="chromium",
                        choices=["chromium", "firefox", "webkit"])
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build a fake ExtractedStep so scene_hooks can read .description / .element_desc
    fake_step = ExtractedStep(
        step_index=0,
        description=args.focus,
        action="click",
        element_desc=args.focus,
    )

    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.set_default_timeout(15_000)

        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)

        apply_hooks(page, fake_step)

        # ── a11y tree ──────────────────────────────────────────────────────────
        raw = page.accessibility.snapshot()
        pruned = _prune(raw) if raw else {}
        (out_dir / "a11y.json").write_text(
            json.dumps(pruned, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── screenshot ─────────────────────────────────────────────────────────
        page.screenshot(path=str(out_dir / "screenshot.png"), full_page=False)

        # ── meta ───────────────────────────────────────────────────────────────
        meta = {
            "url": args.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "viewport": {"width": 1280, "height": 800},
            "focus_kw": args.focus,
        }
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        browser.close()

    _log.info("Snapshot saved to %s", out_dir)
    print(f"OK: {out_dir}/a11y.json + screenshot.png + meta.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 编译检查**

```bash
cd /d/code/TestDemo
python -W error::SyntaxWarning -m py_compile scripts/capture_snapshot.py && echo PASS
```

Expected output: `PASS`

- [ ] **Step 3: 冒烟测试（需能访问网络）**

```bash
python scripts/capture_snapshot.py \
  --url https://www.baidu.com \
  --out .planning/snapshot/smoke_test/ \
  --focus ""
```

Expected: 打印 `OK: .planning/snapshot/smoke_test/a11y.json + screenshot.png + meta.json`  
验证: `ls .planning/snapshot/smoke_test/` 包含 a11y.json、screenshot.png、meta.json 三个文件；a11y.json 不为空 JSON 对象。

- [ ] **Step 4: Commit**

```bash
git add scripts/capture_snapshot.py
git commit -m "feat: add capture_snapshot.py — a11y tree + screenshot for Claude analysis"
```

---

## Task 2: `scripts/verify_locator.py`

**Files:**
- Create: `scripts/verify_locator.py`
- Uses (no-modify): `common/selector_finder/yaml_reuse.py:_yaml_dict_to_spec`, `common/selector_finder/verifier.py:build_locator`

> 接收 JSON 格式的 locator spec，启动无头浏览器验证唯一性，把结果以 JSON 输出到 stdout。Claude 解析此输出决定是否采纳该 locator。

- [ ] **Step 1: 新建文件，写完整实现**

```python
#!/usr/bin/env python
"""
Verify a single locator spec against a live page.

Usage:
    python scripts/verify_locator.py \\
        --url https://example.com \\
        --spec '{"type":"role","role":"button","name":"提交","exact":true}' \\
        [--browser chromium]

Stdout (JSON):
    {"unique": true,  "count": 1, "visible": true,  "error": null}
    {"unique": false, "count": 3, "visible": true,  "error": null}
    {"unique": false, "count": 0, "visible": false, "error": "TimeoutError: ..."}

Spec format examples:
    {"type": "role",        "role": "button", "name": "提交", "exact": true}
    {"type": "css",         "selector": "#OperationForm-btnSubmit"}
    {"type": "text",        "text": "家装", "exact": true}
    {"type": "label",       "label": "用户名", "exact": false}
    {"type": "placeholder", "placeholder": "请输入关键词"}
    {"type": "test_id",     "test_id": "submit-btn"}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from common.selector_finder.verifier import build_locator
from common.selector_finder.yaml_reuse import _yaml_dict_to_spec  # reuse existing parser


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a locator spec on a live page")
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--spec", required=True, help="JSON locator spec")
    parser.add_argument("--browser", default="chromium",
                        choices=["chromium", "firefox", "webkit"])
    args = parser.parse_args()

    try:
        spec_dict = json.loads(args.spec)
    except json.JSONDecodeError as e:
        print(json.dumps({"unique": False, "count": 0, "visible": False,
                          "error": f"invalid JSON: {e}"}))
        return

    spec = _yaml_dict_to_spec(spec_dict)
    if spec is None:
        print(json.dumps({"unique": False, "count": 0, "visible": False,
                          "error": "could not parse spec"}))
        return

    result: dict = {"unique": False, "count": 0, "visible": False, "error": None}

    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch(headless=True)
        page = browser.new_context().new_page()
        page.set_default_timeout(8_000)
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_timeout(1_500)
            locator = build_locator(page, spec)
            count = locator.count()
            result["count"] = count
            if count == 1:
                result["unique"] = True
                try:
                    result["visible"] = locator.first.is_visible()
                except Exception:
                    result["visible"] = False
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        finally:
            browser.close()

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 编译检查**

```bash
python -W error::SyntaxWarning -m py_compile scripts/verify_locator.py && echo PASS
```

Expected: `PASS`

- [ ] **Step 3: 冒烟测试 — role 定位百度搜索框**

```bash
python scripts/verify_locator.py \
  --url https://www.baidu.com \
  --spec '{"type":"css","selector":"#kw"}'
```

Expected stdout: `{"unique": true, "count": 1, "visible": true, "error": null}`

- [ ] **Step 4: 冒烟测试 — 不存在的 selector 返回 count=0**

```bash
python scripts/verify_locator.py \
  --url https://www.baidu.com \
  --spec '{"type":"css","selector":"#this-does-not-exist-xyz"}'
```

Expected stdout: `{"unique": false, "count": 0, "visible": false, "error": null}`

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_locator.py
git commit -m "feat: add verify_locator.py — locator uniqueness check with JSON output"
```

---

## Task 3: `scripts/write_element.py`

**Files:**
- Create: `scripts/write_element.py`

> 将单个元素条目追加写入 yaml 文件。默认拒绝覆盖已有 key，`--force` 可强制覆盖。从 spec JSON 中去掉 `rationale` 字段（AI 输出专用，不写入 yaml）。

- [ ] **Step 1: 新建文件，写完整实现**

```python
#!/usr/bin/env python
"""
Append a single element entry to a YAML elements file.

Usage:
    python scripts/write_element.py \\
        --yaml pages/elements/my_elements.yaml \\
        --key "step3_提交按钮" \\
        --spec '{"type":"css","selector":"#OperationForm-btnSubmit"}' \\
        [--action upload]   # adds action: upload to the entry
        [--force]           # overwrite if key already exists

Exits 1 if key exists and --force not given.
Exits 0 on success; prints: OK: wrote '<key>' to <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Append element to YAML elements file")
    parser.add_argument("--yaml", required=True, dest="yaml_file", help="Path to elements yaml")
    parser.add_argument("--key", required=True, help="Element key, e.g. step3_提交按钮")
    parser.add_argument("--spec", required=True, help="JSON locator spec (rationale field ignored)")
    parser.add_argument("--action", default=None, help="Action override, e.g. 'upload'")
    parser.add_argument("--force", action="store_true", help="Overwrite existing key")
    args = parser.parse_args()

    yaml_path = Path(args.yaml_file)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing content
    existing: dict = {}
    if yaml_path.exists():
        try:
            with yaml_path.open(encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"ERROR: could not read {yaml_path}: {e}", file=sys.stderr)
            sys.exit(1)

    if args.key in existing and not args.force:
        print(
            f"ERROR: key {args.key!r} already exists in {yaml_path}. "
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse spec; remove AI-only fields
    try:
        entry: dict = json.loads(args.spec)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in --spec: {e}", file=sys.stderr)
        sys.exit(1)

    entry.pop("rationale", None)  # AI annotation; not part of BasePage YAML format

    if args.action:
        entry["action"] = args.action

    existing[args.key] = entry

    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"OK: wrote {args.key!r} to {yaml_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 编译检查**

```bash
python -W error::SyntaxWarning -m py_compile scripts/write_element.py && echo PASS
```

Expected: `PASS`

- [ ] **Step 3: 功能测试 — 写入新 key**

```bash
python scripts/write_element.py \
  --yaml /tmp/test_elements.yaml \
  --key "step1_测试按钮" \
  --spec '{"type":"role","role":"button","name":"确定","exact":true}'
```

Expected stdout: `OK: wrote 'step1_测试按钮' to /tmp/test_elements.yaml`  
验证: `cat /tmp/test_elements.yaml` 包含 `step1_测试按钮:` 以及 `type: role`，且无 `rationale` 字段。

- [ ] **Step 4: 功能测试 — 重复 key 被拒绝**

```bash
python scripts/write_element.py \
  --yaml /tmp/test_elements.yaml \
  --key "step1_测试按钮" \
  --spec '{"type":"css","selector":"#new"}' 2>&1; echo "exit:$?"
```

Expected: stderr 包含 `already exists`，且 `exit:1`。

- [ ] **Step 5: 功能测试 — --force 可覆盖**

```bash
python scripts/write_element.py \
  --yaml /tmp/test_elements.yaml \
  --key "step1_测试按钮" \
  --spec '{"type":"css","selector":"#new"}' \
  --force && echo PASS
```

Expected: `OK: wrote 'step1_测试按钮' to /tmp/test_elements.yaml` + `PASS`  
验证: `cat /tmp/test_elements.yaml` 中 `step1_测试按钮` 的值变为 `selector: '#new'`。

- [ ] **Step 6: 功能测试 — upload action 写入**

```bash
python scripts/write_element.py \
  --yaml /tmp/test_elements.yaml \
  --key "step2_上传图片" \
  --spec '{"type":"css","selector":"input[type=\"file\"]"}' \
  --action upload
cat /tmp/test_elements.yaml
```

Expected: yaml 中 `step2_上传图片` 包含 `action: upload`。

- [ ] **Step 7: Commit**

```bash
git add scripts/write_element.py
git commit -m "feat: add write_element.py — atomic YAML element writer"
```

---

## Task 4: 重写 `.claude/skills/ai-selector/SKILL.md`

**Files:**
- Modify: `.claude/skills/ai-selector/SKILL.md`

> 这是 Claude Code 的操作手册，也是整个 v2 的核心调度层。必须包含：完整工作流、9 条规则、候选输出格式、自修复 prompt 模板、特殊场景处理。

- [ ] **Step 1: 完整替换 SKILL.md 内容**

将 `.claude/skills/ai-selector/SKILL.md` 替换为以下完整内容：

```markdown
---
name: ai-selector
description: >
  Use when generating or filling Playwright selectors/locators from test cases or
  element descriptions. Triggers on: "用AI获取selector"、"帮我找元素的selector"、
  "ai-selector"、"fill TODO_SELECTOR"、"自动生成定位器"、"selector_finder"。
  工作模式：Claude 自身读取页面快照（a11y 树 + 截图），按内置规则生成并验证 locator，
  写入 pages/elements/*.yaml。无需 API Key，无 LLM 调用代码。
---

# AI Selector Finder v2（Claude-Driven）

## 当前能力

| 阶段 | 状态 |
|------|------|
| yaml 复用：规范化匹配已有 key，verifier 确认 | ✅ |
| 快照抓取：a11y 树（裁剪）+ 截图 → 文件 | ✅ |
| Claude 分析快照 → 3 个候选 locator（9 条规则）| ✅ |
| 验证：verify_locator.py → JSON 结果 | ✅ |
| 自修复：失败时按错误类型重新分析，重试 1 次 | ✅ |
| 人工兜底：AI 全失败 → find_selectors.py | ✅ |
| 特殊场景：上传 / 动态文本 / 加载中 | ✅ |

**流水线**: `yaml 复用 → AI 分析（快照 + 规则）→ 验证 → 自修复 → 人工兜底`

## 前置条件

- 项目根目录已激活 Python 虚拟环境（`.venv/`）
- `playwright install chromium` 已完成
- 工作目录：项目根（`D:/code/TestDemo` 或 `/d/code/TestDemo`）

## 工作流（严格按顺序执行）

---

### Step 1. 确认输入

收集以下信息（缺少任何一项则向用户提问）：

| 参数 | 来源 |
|------|------|
| `TARGET_URL` | 用户指定的目标页面 URL |
| `INPUT` | 测试用例 markdown 文件路径，或 TODO_SELECTOR 的 yaml key 列表 |
| `OUTPUT_YAML` | 写入哪个 `pages/elements/*.yaml` |
| `ELEMENTS_DIR` | 现有 yaml 目录（默认 `pages/elements`）|

如果用户提供了 `tests/data/xxx.md` 用例文件，从中提取步骤：

```python
import sys; sys.path.insert(0, ".")
from common.selector_finder.extractor import extract_steps_from_file
steps = extract_steps_from_file("tests/data/xxx.md")
for s in steps:
    print(s.step_index, s.element_desc, s.action)
```

---

### Step 2. yaml 复用检查

对每个待处理元素，先查已有 yaml：

```python
import sys; sys.path.insert(0, ".")
from common.selector_finder.yaml_reuse import find_existing
result = find_existing("<element_desc>", "pages/elements")
print(result)  # (LocatorSpec, action) or None
```

- **命中** → 直接用 `write_element.py` 写入 OUTPUT_YAML（key 已存在则跳过），标记 source=yaml_reuse
- **未命中** → 进入 Step 3

---

### Step 3. 抓页面快照

对每个未命中元素，运行：

```bash
python scripts/capture_snapshot.py \
  --url <TARGET_URL> \
  --out .planning/snapshot/step_<N>/ \
  [--focus "<元素描述关键词，如 上传、加载>"]
```

然后用 Read 工具读取：
- `.planning/snapshot/step_<N>/a11y.json`
- `.planning/snapshot/step_<N>/screenshot.png`

---

### Step 4. 生成候选 locator（核心分析）

读取快照后，按以下 **9 条规则** 为目标元素生成 **3 个候选**：

#### 9 条规则（必须严格遵守）

1. **优先级（必须按此顺序选择）**：
   `test_id > role+name > label > placeholder > text > css`

2. **禁止绝对路径 CSS/XPath**（如 `html > body > div:nth-child(3) > button`）

3. **禁止动态 ID 和 hash 类名**（如 `#btn-123456`, `.css-1x8dfjg`, `.sc-abcXYZ`）

4. **优先链式定位**：先定位父容器，再在容器内定位子元素
   - 用 `scope` 字段指定父容器 CSS
   - 示例：`{"type":"role","role":"button","name":"确定","scope":"[class*='Modal']"}`

5. **优先 filter() 思路**：如果角色/文本重复，用 scope 限定范围，而非写复杂 CSS

6. **必须唯一匹配**，禁止依赖 `first()/last()/nth()`（除非唯一手段）

7. **getByRole 必须带 name**，优先 `exact: true`

8. **输出 3 个候选**，按规则 1 的优先级从高到低排列

9. **每个候选附 rationale**（选择原因，供自修复参考）

#### 输出格式（必须用此 JSON 结构）

```json
[
  {
    "type": "role",
    "role": "button",
    "name": "提交",
    "exact": true,
    "rationale": "按钮有明确 name，role+name 语义稳定"
  },
  {
    "type": "css",
    "selector": "#OperationForm-btnSubmit",
    "rationale": "稳定 ID，不含动态数字或 hash"
  },
  {
    "type": "label",
    "label": "提交表单",
    "exact": false,
    "rationale": "aria-label 关联，备用"
  }
]
```

---

### Step 5. 逐一验证候选

对每个候选，运行（注意 JSON 中的引号要用单引号包裹）：

```bash
python scripts/verify_locator.py \
  --url <TARGET_URL> \
  --spec '<候选 JSON（单个对象，不含 rationale）>'
```

结果解析：
- `"unique": true` → 采用此 locator，进入 Step 7
- `"unique": false` → 尝试下一个候选
- 所有候选失败 → 进入 Step 6 自修复

---

### Step 6. 自修复（仅触发一次）

收集所有失败信息，按以下模板重新分析：

```
目标元素：<element_desc>
动作：<action>

上次候选全部失败：
  候选1 <spec1>: count=<N>, error=<msg>
  候选2 <spec2>: count=<N>, error=<msg>
  候选3 <spec3>: count=<N>, error=<msg>

根据以下规则重新给出 3 个新候选（不得与上次重复）：
- count > 1 → 必须加 scope 父容器 CSS 缩小范围
- TimeoutError → 元素在弹窗/动态加载后出现，改选更稳定的祖先节点或 test_id
- count = 0，name 相关 → 改 exact: false，或截取更短的子串
- not visible → 检查是否被遮挡，考虑先用 popup_clear

重新读 a11y.json，结合截图，给出新的 3 个候选（同样满足 9 条规则）。
```

生成新候选后，再次运行 Step 5 验证。仍失败 → 进入 Step 8 人工兜底。

---

### Step 7. 写入 yaml

候选验证通过后：

```bash
python scripts/write_element.py \
  --yaml <OUTPUT_YAML> \
  --key "<step_index>_<element_desc>" \
  --spec '<通过验证的候选 JSON>' \
  [--action upload]   # 如果 action==upload 时加此参数
```

标记此元素 source=ai，继续处理下一个元素。

---

### Step 8. 人工兜底（AI 失败时）

对仍未解析的元素，告知用户：

```
以下元素 AI 无法自动定位，请运行 find_selectors.py 手动点选：
  [步骤N] <element_desc>

命令：
python scripts/find_selectors.py \
  --url <TARGET_URL> \
  --input <INPUT_FILE> \
  --output <OUTPUT_YAML>
```

---

### Step 9. 汇总报告

向用户输出：

```
[完成] selector 生成报告
  yaml 复用:  N 个（无需快照）
  AI 生成:    N 个（含自修复 N 个）
  人工兜底:   N 个（需运行 find_selectors.py）
  输出文件:   <OUTPUT_YAML>

未解析元素：
  [步骤N] <element_desc>   ← 需人工处理
```

---

## 特殊场景处理

### 场景一：上传按钮

触发条件：元素描述含"上传"/"截图"/"图片"/"文件"/"upload"/"attach"

```bash
# capture 时加 --focus 上传（触发 upload_detect 场景钩子）
python scripts/capture_snapshot.py --url X --out .planning/snapshot/stepN/ --focus 上传

# write 时加 --action upload
python scripts/write_element.py --yaml X --key Y --spec '{"type":"css","selector":"input[type=\"file\"]"}' --action upload
```

若 a11y 树中看到 `input[type=file]`，优先用：
```json
{"type": "css", "selector": "input[type=\"file\"]"}
```
或带更精确父容器：
```json
{"type": "css", "selector": "#uploadWrapper input[type=\"file\"]"}
```

### 场景二：动态文本（数字/状态切换词）

⚠ **不稳定示例**：`{"type":"text","text":"6生成"}` — 数字会变

改用：
- `test_id`（最优）
- `css` 用稳定 ID（如 `#OperationForm-btnSubmit`）
- `role+name` 配合短且固定的文本子串

### 场景三：动态加载内容（SPA / 无限滚动）

```bash
# capture 时加 --focus 加载（触发 wait_network_idle 钩子）
python scripts/capture_snapshot.py --url X --out .planning/snapshot/stepN/ --focus 加载
```

---

## 核心模块位置

| 模块 | 路径 |
|------|------|
| 快照抓取 | `scripts/capture_snapshot.py` |
| 定位器验证 | `scripts/verify_locator.py` |
| yaml 写入 | `scripts/write_element.py` |
| 人工兜底入口 | `scripts/find_selectors.py` |
| yaml 复用 | `common/selector_finder/yaml_reuse.py` |
| 场景钩子 | `common/selector_finder/scene_hooks.py` |
| 唯一性验证 | `common/selector_finder/verifier.py` |
| 人工点选 | `common/selector_finder/human_picker.py` |

## 不做的事

- 不调用任何 LLM API（无 API Key，无 SDK）
- 不修改 `pages/elements/*.yaml` 中已有非 TODO 的 key
- 不把含 hash class（`.btn_a3f9c2`）写入 yaml
- 不把动态文本（"6生成"、"剩余 N 个"）作为主定位策略
- 不在脚本内做调度逻辑（调度在此 SKILL.md 中）
```

- [ ] **Step 2: 确认文件内容保存后无语法错误**

```bash
python -c "
import re
content = open('.claude/skills/ai-selector/SKILL.md', encoding='utf-8').read()
assert 'ANTHROPIC_API_KEY' not in content, 'API KEY 仍然存在'
assert 'anthropic' not in content.lower(), 'anthropic 引用仍然存在'
assert 'capture_snapshot.py' in content, '缺少 capture_snapshot 引用'
assert 'verify_locator.py' in content, '缺少 verify_locator 引用'
assert 'write_element.py' in content, '缺少 write_element 引用'
assert '9 条规则' in content, '缺少 9 条规则'
assert '自修复' in content, '缺少自修复模板'
print('PASS: SKILL.md 内容验证通过')
"
```

Expected: `PASS: SKILL.md 内容验证通过`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/ai-selector/SKILL.md
git commit -m "feat: rewrite ai-selector SKILL.md — Claude-driven workflow, 9 rules, self-repair template"
```

---

## Task 5: 集成冒烟测试

**Files:** 无新文件，验证 Task 1-4 整体串联

> 用百度首页（公开可访问）验证 3 个脚本端到端可运行。这是最简化的串联验证，不需要登录。

- [ ] **Step 1: 全量编译检查**

```bash
cd /d/code/TestDemo
python -W error::SyntaxWarning -m py_compile \
  scripts/capture_snapshot.py \
  scripts/verify_locator.py \
  scripts/write_element.py && echo "ALL COMPILE PASS"
```

Expected: `ALL COMPILE PASS`

- [ ] **Step 2: 端到端流程测试**

模拟 Claude 分析流程的工具层：

```bash
# 1. 抓快照
python scripts/capture_snapshot.py \
  --url https://www.baidu.com \
  --out .planning/snapshot/e2e_test/

# 2. 验证一个真实存在的 locator
python scripts/verify_locator.py \
  --url https://www.baidu.com \
  --spec '{"type":"css","selector":"#kw"}'
# 期望: {"unique": true, "count": 1, "visible": true, "error": null}

# 3. 验证一个不存在的 locator
python scripts/verify_locator.py \
  --url https://www.baidu.com \
  --spec '{"type":"css","selector":"#nonexistent-xyz-abc"}'
# 期望: {"unique": false, "count": 0, ...}

# 4. 写入一个元素
python scripts/write_element.py \
  --yaml .planning/snapshot/e2e_test/test_output.yaml \
  --key "step1_搜索框" \
  --spec '{"type":"css","selector":"#kw"}'
# 期望: OK: wrote 'step1_搜索框' to .planning/snapshot/e2e_test/test_output.yaml

# 5. 验证写入结果
cat .planning/snapshot/e2e_test/test_output.yaml
# 期望包含: step1_搜索框: {selector: '#kw', type: css}
```

- [ ] **Step 3: 检查 .planning/snapshot/e2e_test/ 输出结构**

```bash
ls .planning/snapshot/e2e_test/
# 期望包含: a11y.json  screenshot.png  meta.json  test_output.yaml

python -c "
import json, sys
data = json.load(open('.planning/snapshot/e2e_test/a11y.json', encoding='utf-8'))
assert isinstance(data, dict), 'a11y.json 应为 dict'
assert 'role' in data, 'a11y.json 根节点应有 role 字段'
print('a11y.json 结构 PASS:', data.get('role'), '/', data.get('name', '')[:30])
"
```

Expected: `a11y.json 结构 PASS: WebArea / ...`

- [ ] **Step 4: 验证 anthropic / API Key 零引用**

```bash
grep -r "anthropic" /d/code/TestDemo/common/selector_finder/ && echo "FAIL: found anthropic" || echo "PASS: no anthropic refs"
grep -r "ANTHROPIC_API_KEY" /d/code/TestDemo/ --include="*.py" --include="*.md" --exclude-dir=".git" && echo "FAIL: found API_KEY" || echo "PASS: no API_KEY refs"
```

Expected:
```
PASS: no anthropic refs
PASS: no API_KEY refs
```

- [ ] **Step 5: 最终 Commit**

```bash
git add .planning/snapshot/e2e_test/
git commit -m "test: add e2e smoke test artifacts for ai-selector v2 scripts"
```

---

## 自检：Spec 覆盖率

| Spec 需求 | 覆盖 Task |
|-----------|-----------|
| capture_snapshot.py — a11y 树 + 截图 + meta | Task 1 |
| verify_locator.py — JSON stdout | Task 2 |
| write_element.py — 追加不覆盖 | Task 3 |
| SKILL.md — 9 条规则 | Task 4 |
| SKILL.md — 自修复 prompt 模板 | Task 4 |
| SKILL.md — 特殊场景（上传/动态/加载）| Task 4 |
| SKILL.md — 人工兜底流程 | Task 4 |
| 零 API Key / anthropic 引用 | Task 4 Step 2 + Task 5 Step 4 |
| scene_hooks 复用 | Task 1 (capture_snapshot imports apply_hooks) |
| verifier 复用 | Task 2 (verify_locator imports build_locator) |
| yaml_reuse 复用 | Task 2 (verify_locator imports _yaml_dict_to_spec) |
