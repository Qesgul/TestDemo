---
name: clean-artifacts
description: >
  清理本项目执行过程中产生的临时文件和废弃文件。
  触发词："清理无用文件"、"清理临时文件"、"clean artifacts"、"清理废弃脚本"、
  "clean-artifacts"、"清理项目"。
  执行前会列出待删除文件供确认，绝不删除生产代码。
---

# clean-artifacts：临时 & 废弃文件清理

## 临时文件分类定义

| 类别 | 路径模式 | 说明 | 是否安全删除 |
|------|----------|------|-------------|
| AI 分析快照 | `.planning/snapshot/*/` | `capture_snapshot.py` 输出的 a11y.yaml + screenshot.png，每次分析后可重新生成 | ✅ 安全 |
| 调试截图 | `scripts/*.png` | 开发时手动截取的调试图片 | ✅ 安全 |
| 转换报告 | `CONVERSION-REPORT.md` | `case-to-code` skill 自动生成，可随时重新生成 | ✅ 安全 |
| 废弃探索脚本 | `scripts/capture_selectors*.py`、`scripts/capture_aria.py` 等迭代产物 | 被更新版本替代的临时脚本，命名含版本号或序号 | ✅ 安全（确认后） |
| 测试诊断报告 | `diagnostic_reports/` | pytest 失败时自动生成的截图/DOM/网络日志，可重新运行生成 | ✅ 安全 |
| Selector 输入 md | `tests/data/*_selectors.md`、`tests/data/*_selectors_patch.md` | ai-selector 工作流的临时输入文件，yaml 生成后即可删除 | ✅ 安全 |
| pytest 缓存 | `.pytest_cache/`、`__pycache__/` | pytest/Python 自动生成 | ✅ 安全 |
| Allure 产物 | `allure-results/`、`allure-report/` | 测试报告，可重新运行生成 | ✅ 安全 |

## 禁止删除（生产代码）

```
scripts/capture_snapshot.py   ← AI 分析管道：抓快照
scripts/verify_locator.py     ← AI 分析管道：验证 locator
scripts/write_element.py      ← AI 分析管道：写入 yaml
scripts/find_selectors.py     ← 人工兜底入口
common/selector_finder/       ← 核心 selector 逻辑模块
pages/                        ← Page Object 全部文件
tests/                        ← 测试用例全部文件
data_types/                   ← 数据类型定义
.claude/skills/               ← Claude skill 定义
.claude/agents/               ← agent 定义
.claude/playbooks/            ← 踩坑库知识
docs/                         ← 设计文档 / 实施计划
```

---

## 工作流（严格按顺序执行）

### Step 1. 扫描待清理文件

运行以下命令，列出所有临时文件：

```bash
# 1. AI 快照目录（忽略 .gitkeep）
find .planning/snapshot -mindepth 2 -type f ! -name '.gitkeep' 2>/dev/null | sort

# 2. 脚本目录下的调试截图
find scripts -name "*.png" 2>/dev/null

# 3. 转换报告
ls CONVERSION-REPORT.md 2>/dev/null

# 4. pytest / Python 缓存（统计大小）
du -sh .pytest_cache __pycache__ 2>/dev/null

# 5. 废弃探索脚本（有序号 / 版本号的）—— 需要人工确认
git status --short scripts/ | grep "^??" | head -20
```

### Step 2. 向用户展示待删除列表

将 Step 1 扫描结果整理成表格，分两组展示：

**A 组（安全，无需确认）**：快照、调试截图、转换报告、pytest 缓存

**B 组（需确认）**：废弃探索脚本（git 未追踪的 `.py` 文件）

说明：「B 组文件我会逐一确认是否为废弃品，是则删除，否则跳过。」

### Step 3. 执行清理

**A 组**（直接执行）：

```bash
# 快照
rm -rf .planning/snapshot/*/

# 调试截图
find scripts -name "*.png" -delete

# 转换报告
rm -f CONVERSION-REPORT.md

# pytest / Python 缓存
find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache
```

**B 组**（逐文件确认）：
- 读取文件头部注释（前 5 行）判断用途
- 如果是明确的探索/调试脚本（含"临时"、"第N轮"、"第二轮"等字样）→ 删除
- 如果用途不明确 → 跳过，报告中标注「保留-待人工确认」

### Step 4. 检查 .gitignore

确保以下规则已存在（防止同类文件再次入库）：

```gitignore
.planning/snapshot/
scripts/*.png
CONVERSION-REPORT.md
```

如有缺失，追加到 `.gitignore` 对应区块。

### Step 5. 验证项目完整性

```bash
# 编译检查核心文件
python -m py_compile scripts/capture_snapshot.py
python -m py_compile scripts/verify_locator.py
python -m py_compile scripts/write_element.py
python -m py_compile scripts/find_selectors.py

# 确认测试可收集
pytest --collect-only -q 2>&1 | tail -5
```

任一失败 → 立即停止，恢复已删除文件（`git checkout -- <file>`），报告错误。

### Step 6. 汇总报告

```
[完成] 清理报告
  删除文件数：  N 个（其中快照 N、截图 N、废弃脚本 N）
  释放空间：    约 N MB
  保留（待确认）：N 个文件（见下方列表）
  .gitignore 规则：已补充 / 无需变更

编译验证：✅ 通过
测试收集：✅ X 个 items 可收集
```

---

## 不做的事

- 不删除 `pages/`、`tests/`、`common/`、`data_types/`、`scripts/` 下的生产脚本
- 不删除 git 已追踪的文件（除非用户明确要求）
- 不清空 `utils/`（含用户手工维护的工具脚本）
- 不修改或删除 `.claude/` 内的 skill 定义
- 不删除 `.claude/agents/`、`.claude/playbooks/`（agent 定义与踩坑库）
