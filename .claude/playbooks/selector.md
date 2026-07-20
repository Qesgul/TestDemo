# 问题域：selector 定位与验证

## 速查规则

| 现象 | 直接做 | 不要做 |
|---|---|---|
| selector 看似可用但点错元素 | 用 `scripts/verify_locator.py --specs-json` 验证 `count == 1` | 用 `count > 0` 放行 |
| 同名 hash class 多命中 | 加稳定父容器 scope，必要时用标准 CSS 结构伪类 | 直接 `.first()` / `.nth()` 糊过去 |
| 展开下拉后 selector 多命中 | 在目标交互状态重新验证 count | 只在初始页面验证 |
| 判断选中态全都为 True | 看选项父容器 class 是否含 `active/selected/checked` | 用子元素 `activeIcon` count 判断 |
| `is_visible(timeout=...)` 不等待 | 等待用 `wait_for()` / `expect()`；即时判断才用无参 `is_visible()` | 给 `is_visible/is_enabled/is_checked` 传 timeout |

## selector 唯一性必须 count==1

### 速查
- **看到这个现象**: `count>0` 校验通过，但运行时命中错误元素或多元素。
- **直接做**: 用 `scripts/verify_locator.py --specs-json <to_verify.json>` 或 `common/selector_finder/verifier.build_locator`，只接受 `count == 1`。
- **不要做**: 禁止用 `count > 0` 作为 selector 可用标准。
- **适用场景**: `selector-debug`。
- **最近验证日期**: 2026-06-09

### 详情
- **根因**: `count>0` 只能证明页面存在匹配，不能证明唯一；同名 class / 同结构元素会被漏判。
- **处理**: 多命中时加 scope 父容器、语义属性或稳定 CSS 结构，重新验证。

## 同名 hash class 用 CSS 结构定位

### 速查
- **看到这个现象**: 构建产物 hash class 多个兄弟元素共用，单靠 class 无法唯一定位。
- **直接做**: 用父容器 + 标准 CSS 结构伪类，例如 `.promo_wrapper > .promo_package_option:first-child`，再验证 `count == 1`。
- **不要做**: 不用 `page.locator(".promo_package_option").first()` 作为长期方案。
- **适用场景**: `selector-debug`。
- **最近验证日期**: 2026-06-09

### 详情
- **根因**: hash class 不携带语义，且常被多个元素复用。
- **补充**: `:first-child` / `:nth-child(n)` 是 CSS 结构伪类，不是 Playwright `.first()` 链式调用。

## 展开/交互后重新验证命中数

### 速查
- **看到这个现象**: 初始状态 `count=1`，展开下拉或弹窗后变成 `count=3+`。
- **直接做**: 在目标状态验证 selector；YAML 用 `scope` 限定父容器，PageObject 用嵌套 locator。
- **不要做**: 不要只在初始页面截图或 DOM 状态下验证。
- **适用场景**: `selector-debug` / `code-engineer`。
- **最近验证日期**: 2026-07-07

### 详情
```yaml
model_option_item:
  type: css
  selector: '[class*="mode__"]'
  scope: '[class*="agentSelectPopoverContent"]'
```

```python
panel = self.get_locator("model_dropdown_panel").first
options = panel.locator('[class*="mode__"]')
```

## 选中态看父容器 class

### 速查
- **看到这个现象**: 用 `activeIcon` 子元素判断选中态，所有选项都返回 True。
- **直接做**: 读取选项容器自身 class，判断是否包含 `active` / `selected` / `checked`。
- **不要做**: 不用子元素图标数量判断选中态。
- **适用场景**: `code-engineer` / `selector-debug`。
- **最近验证日期**: 2026-07-08

### 详情
```python
# 错误：activeIcon 每项都有
is_active = option.locator('[class*="activeIcon"]').count() > 0

# 正确：看容器 class
is_active = "active" in (option.get_attribute("class") or "").lower()
```

## Playwright 立即型 API 不接 timeout

### 速查
- **看到这个现象**: `Locator.is_visible(timeout=500)` 看似写了等待，但仍立即返回。
- **直接做**: 即时判断用无参 `is_visible()`；等待用 `locator.wait_for(state="visible", timeout=...)` 或 `expect(locator).to_be_visible(timeout=...)`。
- **不要做**: 不给 `is_visible/is_enabled/is_checked` 传 timeout。
- **适用场景**: `selector-debug` / `gio-tracking` / `code-engineer`。
- **最近验证日期**: 2026-06-16

### 详情
- **根因**: Playwright Python 的 `is_*` 系列是即时状态查询，等待语义属于 `wait_for` / `expect`。
- **出处**: `conftest.py` teardown 曾误写 `is_visible(timeout=500)`，已改为 `is_visible()`。

---

## 弹窗状态残留阻塞下一条用例

### 速查
- **看到这个现象**: 上条用例打开 `DownloadConfirmModal` 后未显式关闭，下一条 `wait_for_download_dialog` 超时。
- **直接做**: 在 `logged_in_page` fixture teardown 中、`page.close()` 前点击 `[class^="DownloadConfirmModal__btnClose__"]`，向服务端发送取消信号。
- **不要做**: 不只关闭 page；不依赖模块级 autouse fixture 在 page 已关闭后补救。
- **适用场景**: `code-engineer` / `test-runner` / `selector-debug`。
- **最近验证日期**: 2026-06-16

### 详情
- **根因**: fixture teardown LIFO 导致 `logged_in_page` 先关 page，模块级 `_auto_close_download_dialog` 后执行时已经关不到弹窗，服务端"下载流程进行中"短暂残留。
- **注意**: 判断关闭按钮可见性用无参 `is_visible()`。
- **验证**: VIP 账号两轮多组连续开弹窗用例，级联超时零复发。
