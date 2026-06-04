---
name: case-to-code
description: Use when the user provides a Markdown test case document (table form with columns 用例编号/标题/优先级/前置条件/测试步骤/预期结果) and asks to generate Playwright + pytest automation code into this TestDemo project. Generates the required 5 file types (element YAML, Page Object, dataclass, test data YAML, pytest test file) following the project's existing POM/data/assertion conventions, with explicit TODO placeholders for selectors that cannot be inferred. Triggers on phrases like "把这份用例转成自动化代码"、"根据 markdown 用例生成 pytest"、"convert these test cases to automation"、"generate test code from this MD".
---

# Markdown 用例 → 自动化代码 转换约定（testA）

将外部 Markdown 测试用例（表格 / TSV 形式）转换为本仓库可直接 `pytest` 运行的代码。
本 skill 是 **Claude 专用**，与 Cursor IDE 的 `.cursor/rules/*.mdc` 无关。

> 本规则只补充转换流程约束。POM / 数据 / 用例本身的细节仍以 `.cursor/rules/` 下既有文档为权威：
> - `pageobject-conventions.mdc`
> - `test-suite-conventions.mdc`
> - `test-data-conventions.mdc`
> - `data-model-conventions.mdc`
> - `test-steps-conventions.mdc`
>
> 冲突时**以这些既有规则为准**，本 skill 只做"转换 / 生成 / 占位 / 报告"层的额外约束。

> **埋点用例特别约定**：当待转换用例涉及 GIO 埋点（gio / growingio / `render_*` 事件 / 上报校验 / tracking）时，
> **必须额外先 `Read` `docs/gio埋点自动化生成指南.md`**，并按其「5 步标准流程 + 5 条避坑清单」生成——
> 复用 `gio_tracking` fixture 与 `decode_gio_body`，先探针后断言，不伪造无法触发的事件。

## 触发场景

用户提供 Markdown 测试用例文档（路径或贴入正文），要求生成可在本项目运行的自动化代码。
典型语句：
- "把 `xxx.md` 转成自动化代码"
- "根据这份用例生成 pytest 文件"
- "convert these test cases into automation"

## 输入格式

主结构是 Markdown 表格：`用例编号 | 用例标题 | 优先级 | 前置条件 | 测试步骤 | 预期结果`

- 文档中可能并存同义的 TSV 代码块；**只取表格一份**，避免重复生成。
- 标题/前置/步骤/预期的分隔符常见为中文分号 `；`、阿拉伯数字 `1. 2. 3.`；解析时兼容。
- 用例编号常见格式：`TC-XXX-001`、`REQ-001`、`F1.2` 等。

## 必须产出的文件（按生成顺序）

每接入一个新 feature 时，按以下顺序补齐 4-5 类文件：

| # | 文件 | 必填 |
|---|------|------|
| 1 | `pages/elements/{feature}_elements.yaml` | ✅ |
| 2 | `pages/methods/{feature}_page.py` | ✅ |
| 3 | `data_types/{feature}_data_types.py` | 仅当用例需要参数化 |
| 4 | `tests/data/{feature}_data.yaml`（必须包含 `cases` 键，可为空数组） | ✅ |
| 5 | `tests/cases/test_{feature}.py` | ✅ |

`{feature}` 命名：取 Markdown 文件名或 PRD 名称的英文/拼音简写，**全小写下划线**，长度 ≤ 16 字符（例：`atm_render`、`workflow_route`）。

## 步骤翻译策略（严格按优先级）

每条 Markdown 步骤生成代码时按以下顺序匹配：

| 优先级 | 来源 | 命中后的代码形态 |
|------|------|------|
| ① | `pages/methods/*_page.py` 已有方法（语义匹配） | `xxx_page.method()` |
| ② | 没有现成方法 → 在对应 `_page.py` 末尾追加方法骨架 | 新方法签名 + docstring + `self.get_locator(...)` |
| ③ | 没有现成 YAML key → 在对应 `_elements.yaml` 追加 key，selector 留 `'TODO_SELECTOR'` 并附注释 | YAML 新增条目 |
| ④ | 仍未能映射 → 在用例代码处使用 `# TODO[locate]: <步骤原文>` 占位 | 注释 + `pytest.skip` 或断言占位 |

**禁止**：
- 在 `tests/cases/test_*.py` 内直接写 CSS/XPath 选择器
- 在 `pages/methods/*_page.py` 方法体内硬编码 selector（必须经 `self.get_locator(...)`，兜底场景须注释说明）
- 使用 `expect(...)` 直接断言，统一改用 `assertion` fixture
- **不允许**直接把 `text=xxx` 当成"已确认 selector"写入 yaml；必须经过浏览器实抓 / codegen 验证唯一命中后才能落 yaml，否则一律走 `'TODO_SELECTOR'` 占位

## 现场抓元素操作指引（替代"猜 selector"）

按下面的优先级补 selector，命中即停：

| 优先级 | 来源 | 触发条件 / 操作 |
|------|------|------|
| ① | 现有 `pages/elements/*.yaml` 的 key | 文本/语义匹配命中 |
| ② | **MCP 浏览器实抓** | 用户已开启 Chrome 扩展、URL 可访问。Claude 调用 `mcp__Claude_in_Chrome__find` / `read_page` 直接拿元素 ref，并选择稳定的 `role=` / `text=` / `data-*` 类 selector 写入 yaml |
| ③ | **`playwright codegen`**（用户自驱） | 命令模板：`python -m playwright codegen <url>`；用户操作完，把生成的 selector 贴回对话，Claude 写入 yaml |
| ④ | `'TODO_SELECTOR'` + 报告高亮 | 以上均不可用时使用，CONVERSION-REPORT.md 中显式列出 |

约束：
- 所有走 ②/③ 抓回的 selector，写入 yaml 前必须在浏览器中验证"唯一命中"。
- 优先选择稳定语义定位（`role=`、`text=`、`data-testid`、`aria-label`），避免使用带 hash 的 class（如 `.btn_a3f9c2`）。

## 登录前置统一规则

> **优先用 `logged_in_page` fixture**：前置是"已登录"且不测登录本身的用例，fixture 直接用
> `logged_in_page`（会话级 cookie 登录，复用 context），用例内不再写 `goto_login`/`login_with`，
> 也不因"需登录"就 skip（详见 `test-suite-conventions` 「登录态用例」规则 4）。
> 下方 `login_with` 写法仅用于**显式测试登录流程本身**的用例。

```python
# ✅ 需登录态的业务用例（埋点、福利、个人中心…）
def test_xxx(self, logged_in_page, assertion):
    landing = XxxPage(logged_in_page)
    landing.goto()
    ...

# ✅ 测登录流程本身的用例（仍用 page）
def test_login_success(self, page, assertion):
    login_page = LoginPage(page)
    login_page.goto_login_page()
    login_page.login_with(_DATA["username"], _DATA["password"])
```

- `login_with` 已实现 cookie 优先 + 密码兜底（见 `pages/methods/login_page.py:151`），**不要**在新 Page 类里重复实现登录或 cookie 操作。
- `username` / `password` 从 `tests/data/{feature}_data.yaml` 根级取，**禁止**硬编码。

## 页面入口规则（强约束）

URL **只在 Page 类里**配置一次，作为类属性 `DEFAULT_URL`，并提供无参 `goto()`：

```python
class AtmRenderPage(BasePage):
    DEFAULT_URL = "https://example.com/xxx"  # 唯一 URL 配置点

    def goto(self, url: Optional[str] = None, **kwargs) -> None:
        super().goto(url or self.DEFAULT_URL, **kwargs)
```

约束：
- **导航入口 URL**（`goto()` 使用的 URL）只在 `Page.DEFAULT_URL` 里配一次，**不在 yaml 中重复**。
- 用例层一律写 `xxx_page.goto()`，不再把入口 URL 作为参数传入用例。
- 切换环境用 `BASE_URL` 环境变量在 Page 内部拼接，不暴露到用例层。
- 已有 Page 接入新用例时，若仍用旧 `goto_xxx_page(url)`，**必须**顺手迁移为本规则。

**可以**在 yaml 里出现的 URL 场景（不与 Page 重复的）：
- 断言用的期望跳转 URL（如登录后重定向地址 `expected_redirect_url`）
- 外链校验（如分享链接、第三方跳转目标）
- 参数化的子路径（不同用例对应不同详情页 URL）

## 数据规则

- 账号、文案期望、参数化数据等放 `tests/data/{feature}_data.yaml` **根级**键。
- **账号字段（username / password）必须经由账号池解析**（见 Step 4.5 + `.claude/skills/account-pool/SKILL.md`），禁止直接硬写一个从未在池子里登记的账号；如池子无匹配，先补池子再继续。
- **导航入口 URL 不放 yaml**（见上节「页面入口规则」）；断言用的期望 URL / 跳转 URL 等非重复配置可放 yaml。
- 参数化用例放 `cases` 列表，字段与 `data_types/{feature}_data_types.py` 中 dataclass 一一对应。
- 期望值不在测试方法里写死，统一从 `_DATA[...]` 或 `case_data.xxx` 取。

## Checkpoint Name 自动补全（2026-05-27）

生成 `assertion.assert_*` 时，**必须**通过 composer 推断 `name=`，禁止手写无意义名称。

### 调用方式（Step 6 生成测试文件时，对每个步骤+预期对执行）

```bash
python -c "
import sys, json
sys.path.insert(0, '.')
from common.checkpoint_name.composer import compose
from common.checkpoint_name.parser import parse_step, parse_expect
step = parse_step(<idx>, '<步骤原文>')
expect = parse_expect(<idx>, '<预期原文>')
result = compose(step, expect)
print(json.dumps({'name': result.name, 'tier': result.tier, 'todo': result.todo}, ensure_ascii=False))
"
```

### 结果处理规则

| tier | 含义 | 处理方式 |
|------|------|---------|
| 1 | 作者显式指定 `[name: xxx]` | 直接用 `name` 字段值 |
| 2 | step.object + expect.field 组合 | 直接用 `name` 字段值 |
| 3 | 仅 step.object | 直接用 `name` 字段值 |
| 4 | 仅 expect.field（含字典 miss）| 直接用 `name`；若 `todo` 非空，在断言行**上方**加 `todo` 注释 |
| 5 | 兜底（步骤前 8 字）| **Claude 先判断**：能给更精炼业务名则替换；否则保留并加 `# TODO[checkpoint_name]: <todo内容>` |

### Tier 5 示例

composer 返回 `{"name": "等待页面响应", "tier": 5, "todo": "..."}`，Claude 判断无业务语义 → 保留兜底：

```python
# TODO[checkpoint_name]: step: '等待页面响应' | expect: '无报错' — 自动命名兜底，建议手动改名或补充字典
assertion.assert_true(cond, name="等待页面响应", message="...")
```

composer 返回 `{"name": "验证用户标签下拉", "tier": 5, "todo": "..."}`，Claude 能给更好名字 → 替换（不加注释）：

```python
assertion.assert_true(cond, name="设计师标签选项存在", message="...")
```

### 扩充字典

遇到 tier=4 且 todo 含 `checkpoint_dict` 时，在 `common/checkpoint_name_dict.yaml` 的 `fields:` 区追加新字段映射，并在 CONVERSION-REPORT.md 的「字典扩充」一节记录。

---

## 断言规则

- 必须使用 `assertion` fixture：
  - `assertion.assert_true(cond, message="...")`
  - `assertion.assert_equal(actual, expected, message="...")`
  - `assertion.expect_to_be_visible(locator, ...)` 等
- ⚠️ **`assert_equal` 签名陷阱**：第 3 位置参数是 `message` 非 `name`；比对断言必须用关键字
  `name=`，否则校验点汇总表丢名（详见 `test-suite-conventions.mdc` 断言教训第 1 条）。
- **禁止** `assert` 裸语句和 `playwright.expect(...)` 直调，否则失败时不会落诊断报告。
- **每个 assertion 必须带 `name=` 参数**，name 取 markdown 用例「预期结果」列对应短句：
  - `assertion.expect_to_have_text(locator, "登录成功", name="登录成功提示文案")`
  - `assertion.assert_equal(actual_url, "/home", name="登录后跳转首页 URL")`
  - 命名规则：≤ 20 字，描述"在校验什么"，不重复期望值本身
- 一条 markdown 步骤含多个隐式校验时，每个 assertion 独立 `name`，按"主校验 / 次校验"分别命名
- 用例执行结束时 stdout 会自动打印「关键校验点汇总表」，`name` 显示在表的「校验点」列；未传 `name` 时用方法名兜底（视觉上以 `·` 前缀展示），降低可读性，**必须避免**

## Marker 映射

按 Markdown 用例优先级映射 pytest 标记：

| 原优先级 | pytest marker（必填） | 附加 marker（按场景） |
|------|------|------|
| P0 | `@pytest.mark.smoke` + `@pytest.mark.main` | `ui` / `popup` 等 |
| P1 | `@pytest.mark.core` + `@pytest.mark.main` | `ui` / `popup` 等 |
| P2 / P3 | `@pytest.mark.ui` | — |

`flaky` / `no_diagnostics` / `quick` 由人工后续评估，**不在自动转换里默认添加**。

## 用例可自动化分级（生成前必做）

每条 Markdown 用例在生成前必须打一个分级标签：

| 分级 | 触发条件 | 处理方式 |
|------|------|------|
| `auto` | 纯 UI 操作 + UI 可断言（可见、文案、选中态） | 直接生成可执行代码 |
| `network` | 涉及"调用工作流 ID"、"接口失败"、"白屏"、"loading"、"调用记录" | 生成代码 + `page.route()` 拦截 / 校验骨架 |
| `env` | 涉及"网络中断"、"弱网"、"CDN"、"离线" | 生成代码 + `context.set_offline()` / 限速骨架 |
| `manual` | 涉及"目视判断"、"对比基准截图"、"大模型识别"、"两端对比"、"【待澄清】" | 生成 `@pytest.mark.skip(reason="manual: ...")` 骨架，仅保留步骤注释 |

`manual` 用例**不要**伪造断言；保留步骤注释 + skip 标记，等待人工接管。

## TODO 占位规范（统一格式，便于 grep）

| 占位 | 用法 |
|------|------|
| `'TODO_SELECTOR'` | YAML 中暂未确认的 selector |
| `# TODO[locate]: <原文>` | 步骤无法翻译时在用例/PO 方法内的注释 |
| `# TODO[url]: ...` | URL 待确认 |
| `# TODO[selector_class]: ...` | 选中态/激活态 class 子串待确认 |
| `# TODO[manual]: ...` | manual 用例的人工说明 |
| `pytest.skip("TODO: ...")` | 整条用例尚不可执行时显式跳过 |
| `# TODO[待考虑]: <原因>` + `pytest.skip("【待考虑】...")` | 需时钟 mock（跨日 `page.clock`）或接口 mock（`route` 返回特定数据）才能自动化；当前暂 skip，留待后续实现；`【待考虑】` 前缀一眼可识别，可 `grep "待考虑"` 批量追踪 |

## 必须产出的转换报告

每次转换结束在仓库根目录写 `CONVERSION-REPORT.md`，至少包含：

1. 输入 Markdown 文件清单
2. 已生成文件清单（与上面 5 类一一对应）
3. 用例分级统计（auto / network / env / manual 各几条）
4. **TODO 清单**：grep `TODO_SELECTOR`、`# TODO[`、`pytest.skip("TODO`
5. 验收命令：
   ```bash
   python -m py_compile pages/methods/{feature}_page.py tests/cases/test_{feature}.py
   pytest --collect-only tests/cases/test_{feature}.py -q
   ```

## 验收门禁（生成完成前必须自检）

转换器最后必须执行下面三步，**任一失败视为转换失败**并在报告中标红：

```bash
python -m py_compile pages/methods/{feature}_page.py
python -m py_compile tests/cases/test_{feature}.py
pytest --collect-only tests/cases/test_{feature}.py
```

`pytest --collect-only` 必须 0 报错；运行时失败（找不到元素、URL 错）允许，但需在 TODO 清单中显式列出。

## 多版本 / 多变体覆盖（参数化优先）

一个操作有多个版本或变体时（如下载含 Win10/Win7、套餐多档、分类多类），**不只测默认项**，参数化覆盖全部：

- **数据 yaml** 列全各变体期望值（`download_btn_data2: {hero_win10: "...", hero_win7: "..."}`）
- **用例** 用 `@pytest.mark.parametrize` 遍历变体，而非为每个变体写一个方法
- **Page 方法** 用 `keyword` 参数区分变体（如 `click_hero_download_version(keyword="Win7")`），禁止为每变体写单独方法

```python
# ✅ 参数化覆盖多版本
@pytest.mark.parametrize("keyword,expected_data2", [
    ("Win10", _DATA["tracking_meta"]["download_btn_data2"]["hero_win10"]),
    ("Win7",  _DATA["tracking_meta"]["download_btn_data2"]["hero_win7"]),
])
def test_download_click_event(self, page, assertion, gio_tracking, keyword, expected_data2):
    landing.click_hero_download_version(keyword=keyword)
    gio_tracking.assert_event("render_download_click", vars={"data2": expected_data2})
```

## 不做的事（明确边界）

- 不消费 PRD / 需求文档；只吃 Markdown 用例
- 不做需求 ID ↔ 用例的反向追溯
- 不做用例去重 / 优先级再分配（由用例作者负责）
- 不为 `manual` 类用例自动写"目视判断"逻辑
- 不修改既有 PO / YAML 中已存在的 key 或方法（**只追加，不覆盖**）

## 工作流（Page-first，强约束）

收到用户输入（**最小输入** = 页面 URL + 用例步骤 + 期望结果，或一份 Markdown 用例文档）后，**严格按以下顺序**推进：

### Step 1. 解析与分级
- 抽取表格行；同义 TSV 块去重；
- 每条用例打 `auto / network / env / manual` 标签；
- 决定 `{feature}` 名（文件名或 PRD 简写，全小写下划线，≤16 字符）。

### Step 2. 确认 / 创建 Page（必须先做）
- 已存在 `pages/methods/{feature}_page.py` → 在末尾**追加**方法（不覆盖既有）；
- 不存在 → 新建：必须包含 `DEFAULT_URL` 类属性 + 无参 `goto()`（见「页面入口规则」）；
- 同时建对应 `pages/elements/{feature}_elements.yaml`（即使先空）。

### Step 3. 抓元素
- 按「现场抓元素操作指引」①→②→③→④ 顺序补全 selector；
- 抓回的 selector **写入 yaml**，不在 Page 方法体里硬编码；
- 仍不可定位 → 在 yaml 写 `'TODO_SELECTOR'` 并在报告中列出。

### Step 4. 在 Page 类实现"步骤动作方法"
- 一条 markdown 步骤 ≈ 一个 Page 方法；
- 方法体只调 `self.get_locator(yaml_key)` + 动作；
- 找不到 selector 的步骤 → 方法骨架 + `# TODO[locate]:` 注释。

### Step 4.5. 账号解析（2026-05-26）

判断用例是否需要登录账号：

- **不需要登录** → 跳过本步骤，data yaml 不写 username/password
- **需要登录** → 走以下路径：

  1. **判断"是否明确指定账号需求"**：
     - Markdown 前置条件只写通用表述（如"已登录"、"已进入系统"、"账号已登录"）→ **走特殊默认路径**：
       直接使用 `tests/data/account_pool.yaml` 中 `tags` 包含 `default` 和 `generic_user` 的账号，不打断用户
     - Markdown 前置条件含具体角色/状态/能力描述（如"VIP 用户"、"已有订单"、"能下载图钉图片"）→ 进 step 2

  2. **提取需求关键词，映射到 snake_case 标签**（遵守 `.claude/skills/account-pool/SKILL.md` 命名约定）：
     ```
     "VIP 已登录用户"          → [vip]
     "有历史订单的用户"         → [has_orders]
     "能下载图钉图片的账号"     → [pin_image_downloader]
     ```

  3. **按账号池匹配算法处理**（严格 AND + 最小超集 + top 3 + 0/1/2~3 决策分支），
     详见 `.claude/skills/account-pool/SKILL.md` 的「匹配算法」段落。

  4. **拿到选中账号** → 把 `username` 和 `password` 写入 `tests/data/{feature}_data.yaml` 根级。

- **0 候选场景** → 不要继续 Step 5，停下让用户补账号入池后再继续；
  详见 `.claude/skills/account-pool/SKILL.md` 的「新增账号工作流」。

### Step 5. 生成 dataclass + 数据 yaml（仅参数化用例需要）
- `data_types/{feature}_data_types.py` + `tests/data/{feature}_data.yaml`；
- yaml 必须含 `cases` 键（可为空数组）；
- **禁止**写入 URL 键。

### Step 6. 生成 `tests/cases/test_{feature}.py`
- 用例方法只编排 Page 方法 + `assertion` 断言；
- 入口统一 `xxx_page.goto()`，不传 url。
- 每个 assertion 调用强制带 `name=`，名字来自 markdown「预期结果」列；详见「断言规则」章节

### Step 7. 验收门禁
```bash
python -m py_compile pages/methods/{feature}_page.py tests/cases/test_{feature}.py
pytest --collect-only tests/cases/test_{feature}.py -q
```
任一失败立即修，不带病提交。

### Step 8. 写 CONVERSION-REPORT.md + 简短汇报
- 列出已生成文件、TODO 清单、用例分级统计；
- 告诉用户生成了什么、TODO 在哪、下一步建议。

### 调试期反馈循环（生成后阶段）
- 元素定位错 → 改 yaml（**不改 test**）
- 行为/时序错 → 改 Page 方法（**不改 test**）
- 用例编排错 → 才改 test
