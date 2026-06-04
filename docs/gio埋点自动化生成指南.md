# GIO 埋点自动化生成指南

> **用途**：下次为任何页面生成 GrowingIO（gio）埋点自动化用例时，按本指南执行可避开历史踩过的坑。
> **配套**：本次实战记录见 `docs/埋点实现复盘.md`；本文件是提炼出的**前瞻性流程 + 避坑清单**。
> **适用项目**：TestDemo（已内建 gio 埋点框架，无需重新造轮子）。

---

## 〇、TL;DR — 一句话原则

1. **先探针，后下结论**：任何"这页面不走 gio / 没有某事件"的判断，必须先跑实况探针解码确认，不能凭 body 明文搜索或 URL 域名猜。
2. **复用现成框架**：项目已有 `gio_tracking` fixture + `decode_gio_body` + `assert_event`，直接用，别自己挂 route。
3. **追踪真实触发路径**：埋点常藏在二级交互（Popover/弹窗/版本选择）里，"点按钮 ≠ 触发埋点"。

---

## 一、5 步标准流程

### Step 1：实况探针，确认埋点真相（**最关键，不可跳过**）

用 stdin heredoc 跑探针（不落文件），监听**所有** POST 请求并用项目解码器尝试解码：

```bash
PYTHONUTF8=1 PYTHONPATH=. .venv/Scripts/python.exe - <<'PY' 2>&1 | tail -40
import sys
sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
from common.tracking.core import decode_gio_body

hits = []
def on_request(req):
    try:
        if req.method != "POST":
            return
        body = req.post_data_buffer        # 必须用 buffer，不是 post_data
        if not body:
            return
        for d in decode_gio_body(body):    # LZString 解码 + json
            if d.get("n"):
                hits.append((req.url, d.get("n"), d.get("var") or {}))
    except Exception:
        pass

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={"width":1366,"height":768}).new_page()
    page.on("request", on_request)
    from pages.methods.<feature>_page import <FeaturePage>
    pg = <FeaturePage>(page); pg.goto(); page.wait_for_timeout(2500)
    # ... 触发各类交互（滚动 / 点击 / 弹窗）...
    page.wait_for_timeout(2000)
    b.close()

# 输出：上报域名 + 事件名 + var
from collections import Counter
print("域名:", Counter(u.split('/')[2] for u,_,_ in hits))
for url, n, var in hits:
    print(f"  {n:28s} data={var.get('data')!r} data2={var.get('data2')!r}")
PY
```

**探针要回答 4 个问题**：
| 问题 | 为什么重要 |
|---|---|
| 上报域名是否含 `growingio.com`？ | `GioTrackingCapture._url_matcher` 默认匹配 `"growingio.com" in url`。若域名不同，需扩 matcher |
| body 能否被 `decode_gio_body` 解码？ | gio 走 LZString 压缩，普通明文搜索一定搜不到 |
| 目标 `render_*` 事件是否真触发？ | 确认 PRD 定义的事件页面真的有埋 |
| 每个事件的 `var.data` / `var.data2` 实际取值？ | 写断言要用真实值，不能照搬 PRD 文字 |

### Step 2：复用 `gio_tracking` fixture（不要自己挂 route）

用例签名直接加 `gio_tracking` 参数即可，fixture 会自动挂 route、解码、累积事件、teardown 打印汇总表：

```python
def test_xxx(self, page, assertion, gio_tracking):
    ...
    gio_tracking.assert_event("render_download_click",
                              vars={"data": "Banner", "data2": "首屏CTA-Win10"})
```

### Step 3：写 `tracking:` YAML 段（数据驱动期望）

在 `tests/data/{feature}_data.yaml` 追加（格式参考 `recharge_flow_data.yaml` / `yunxuan_landing_data.yaml`）：

```yaml
tracking:
  requirement: "功能名 GIO 埋点"
  events:
    - identifier: render_screen_show       # = 上报 body 的 "n" 字段
      name: 页面_屏幕曝光                    # 人类可读名
      trigger: 滚动到对应屏触发
      expect_vars: {data2: "第1屏"}         # 可选，子集匹配
    - identifier: render_case_click
      name: 页面_案例点击
      status: pending                       # 页面未埋/需桩 → pending，不写死断言
      expect_vars: {}
```

### Step 4：接线用例（实装 active，骨架 pending）

- **active 事件**（探针确认触发）→ 真实断言
- **pending 事件**（需登录/接口桩/页面未实现）→ `pytest.skip("pending/...: 原因")`，docstring 写清恢复条件

### Step 5：验收

```bash
PYTHONUTF8=1 PYTHONPATH=. .venv/Scripts/python.exe -m py_compile pages/methods/{feature}_page.py tests/cases/test_{feature}.py
PYTHONUTF8=1 PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/cases/test_{feature}.py::TestXxxTracking -p no:cacheprovider -v
```

---

## 二、5 条避坑清单（症状 → 根因 → 正确做法）

### 坑 1：误判"不走 gio / 走 GA4"
- **症状**：拦截请求里搜不到 `render_*` 事件字符串，以为页面不走 gio
- **根因**：① 在 **LZString 压缩后**的 body 里做明文 `find()`，永远搜不到；② 用 `**/collect**` 等 GA4 路径匹配，漏了 `api.growingio.com/custom/.../cstm`
- **正确做法**：监听全部 POST，用 `decode_gio_body(req.post_data_buffer)` 解码后再判断。gio body 一定要解码

### 坑 2："点按钮 = 触发埋点"想当然
- **症状**：点了 CTA/卡片，等很久也没有对应埋点
- **根因**：埋点藏在二级交互。例：首屏 CTA 点击只是弹出 Ant Popover 版本选择，`render_download_click` 是在**点击 Popover 内版本项**时才上报
- **正确做法**：点击后用 `read_page` / `page.evaluate` 看 DOM 变化（是否冒出 popover/modal），逐步追到真正触发埋点的那一步。写成 Page 方法封装多步交互（如 `click_hero_download_version`）

### 坑 3：元素无 handler 时硬造断言
- **症状**：PRD 要求某卡片点击埋点，但怎么点都不上报
- **根因**：该元素是纯静态 DOM（如 `<div><img></div>`），根本没绑点击事件——**研发没实现这个埋点**
- **正确做法**：用 `el.outerHTML` 确认元素无 `onclick`/无 handler → 判定为**研发缺陷**，标 `status: pending` + `pytest.skip("pending/bug: ...")`，在报告里列为待研发修复项。**绝不伪造断言**

### 坑 4：全量运行时埋点用例偶发 0 事件
- **症状**：单跑通过，全套 60 条跑时类内第一条埋点用例偶发抓不到事件
- **根因**：长时运行（10+ 分钟）后 Chromium 内存压力大，GIO SDK 初始化 + `sendBeacon` 上报变慢，在 `wait_for_timeout` 之后才发出，断言时 `find()` 返回空
- **正确做法**：埋点用例触发动作后**尾部等待给足 ≥3000ms**；曝光类断言用 `>= 5`（容 1~2 条网络丢失）而非 `== 7` 硬等

### 坑 6：登录态埋点不知道用哪个 fixture

- **症状**：事件需登录才触发，直接用 `page` fixture 跑没有上报，于是直接 skip
- **正确做法**：fixture 换成 `logged_in_page`（会话级 cookie 登录，自动复用）；`gio_tracking` 走 `_resolve_active_page`，`logged_in_page` 优先自动 attach，无需额外接线。实战参考：`test_recharge_gio_tracking`。完整规则见 `test-suite-conventions「登录态用例」规则 4`

### 坑 5：探针脚本中文报错
- **症状**：独立 python 脚本 print 含中文/✓ 时 `UnicodeEncodeError: gbk`
- **根因**：Windows 默认 GBK；conftest 的 UTF-8 修复只在 pytest 进程内生效
- **正确做法**：所有独立探针/脚本前缀 `PYTHONUTF8=1`

---

## 三、现成资产地图（直接用，别重写）

| 资产 | 路径 | 用法 |
|---|---|---|
| 解码器 | `common/tracking/core.py` → `decode_gio_body(body)` | LZString → json，返回事件 dict 列表；失败返回 `[]` 不抛异常 |
| 捕获器 | `common/tracking/capture.py` → `GioTrackingCapture` | 挂 route、累积、`assert_event`、打印汇总表 |
| fixture | `conftest.py` → `gio_tracking` | 用例加参数即用，自动 attach/detach + 打印 |
| 期望加载 | `common/tracking/expectations.py` → `load_gio_expectations(yaml)` | 读 `tracking:` 段为对象列表 |
| 实战参考 | `tests/cases/test_recharge_flow.py::test_recharge_gio_tracking` | 登录态埋点的标准写法 |
| 实战参考 | `tests/cases/test_yunxuan_landing.py::TestYunxuanTracking` | 滚动曝光 + 多步点击埋点的标准写法 |

**`gio_tracking` 核心 API**：
```python
gio_tracking.assert_event("事件名")                          # 仅校验触发
gio_tracking.assert_event("事件名", vars={"data2": "第1屏"})  # 触发 + var 子集匹配
gio_tracking.find("事件名")                                  # 返回该事件全部 GioEvent，自己判次数/取 var
# GioEvent: .identifier(=n) / .type(=t) / .vars(=var dict) / .raw
```

**URL matcher 注意**：默认 `"growingio.com" in url`。若探针发现上报域名是自建/代理域名（不含 growingio.com），需在 `capture.py` 的 `_url_matcher` 扩展匹配规则。

---

## 四、可复制用例模板

### 模板 A：滚动曝光类（render_screen_show / render_full_view）
```python
def test_screen_show_events(self, page, assertion, gio_tracking):
    page.set_default_timeout(30000)
    landing = XxxPage(page)
    landing.goto()
    page.wait_for_timeout(2000)

    landing.scroll_through_all_screens()   # 逐屏滚 + 每屏 wait 700ms
    page.wait_for_timeout(3000)            # 尾部给足时间（坑4）

    matched = {e.vars.get("data2") for e in gio_tracking.find("render_screen_show")}
    assertion.assert_true(len(matched) >= 5, name="各屏曝光>=5屏",
                          message=f"覆盖屏：{sorted(matched)}")
```

### 模板 B：点击类（可能含多步交互）
```python
def test_download_click_event(self, page, assertion, gio_tracking):
    page.set_default_timeout(30000)
    landing = XxxPage(page)
    landing.goto(); page.wait_for_timeout(2500)

    landing.click_hero_download_version(keyword="Win10")  # 封装多步：CTA → popover 版本项
    page.wait_for_timeout(1500)

    gio_tracking.assert_event("render_download_click",
                              vars={"data": "Banner", "data2": "首屏CTA-Win10"})
```

### 模板 C：渠道/参数映射类
```python
def test_channel_data_value(self, page, assertion, gio_tracking):
    landing = XxxPage(page)
    landing.goto(url="https://.../page.html?fromwhere=0")   # 不同参数不同渠道
    page.wait_for_timeout(2000)
    landing.scroll_through_all_screens(); page.wait_for_timeout(1200)

    events = gio_tracking.find("render_screen_show")
    banner = [e for e in events if e.vars.get("data") == "Banner"]
    assertion.assert_true(len(banner) >= 1, name="fromwhere=0渠道data=Banner")
```

---

## 五、快速决策表

| 探针结果 | 处理 | YAML status | 用例形态 |
|---|---|---|---|
| 事件触发 ✅ + var 可读 | **实装** | `active`（默认） | 真实 `assert_event` |
| 需登录态 / 接口桩才触发 | pending | `pending` | `pytest.skip("pending/login\|stub: ...")` |
| 元素无 handler，从不上报 | **研发缺陷** | `pending` + 缺陷注释 | `pytest.skip("pending/bug: 页面未埋")` + 报告列缺陷 |
| 上报域名非 growingio.com | 先扩 matcher | active | 改 `capture.py` 后实装 |

---

## 六、一页 checklist（开工前过一遍）

- [ ] 跑探针，解码确认上报域名 + body 编码 + 事件名 + var 真实取值
- [ ] 确认上报域名含 `growingio.com`（否则扩 `_url_matcher`）
- [ ] 用例加 `gio_tracking` 参数，不自己挂 route
- [ ] `tracking:` YAML 段 identifier = 真实 `n` 字段
- [ ] 多步触发的埋点封装成 Page 方法
- [ ] 触发后尾部等待 ≥3000ms，曝光断言用 `>=` 容错
- [ ] 无法触发的事件区分：需桩 → pending / 页面未埋 → 报缺陷，不伪造断言
- [ ] 探针/脚本加 `PYTHONUTF8=1`
- [ ] 验收：py_compile + 单独跑 Tracking 类
