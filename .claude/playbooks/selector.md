# 问题域：selector 定位与验证

## selector 唯一性必须 count==1，禁用 count>0
- **问题域**: selector唯一性
- **症状**: 用宽松的 `count>0` 判定 selector「有效」，结果同名 class 多命中被漏判，运行时定位到错误元素（如本次 `promo_package_option` 实际 count=3，却被当成功）。
- **根因**: `count>0` 只要页面上有任意一个匹配就通过，无法发现「同名 class / 同结构多元素」造成的多命中；真正可靠的判定是「页面上有且仅有一个匹配」。
- **解决方案**: 用官方工具验证唯一性，判定标准严格为 `count==1`：
  - `python scripts/verify_locator.py --specs-json <to_verify.json>`，读输出里的 `unique`/`count`，只接受 `count==1`。
  - 或代码内 `common/selector_finder/verifier.build_locator` 构造后断言 `count==1`。
  - **禁止** 用 `count>0` 放行，多命中一律视为未通过，进同批自修复（加 scope 父容器缩小范围）。
- **适用 agent**: selector-debug
- **最近验证日期**: 2026-06-09

## 同名 hash class 无法区分时，用标准 CSS 结构定位而非 .first()
- **问题域**: selector同名hash
- **症状**: 目标元素的 class 是构建产物 hash（如 `.promo_package_option_a3f9c2`），页面上多个兄弟元素共用同一 hash class，无法靠 class 单独定位到唯一的那个。
- **根因**: hash class 不携带语义、且多元素复用，单层选择器必然多命中；ai-selector 规则3 禁止把 hash class 作为定位依据，规则6 禁止依赖 `first()/last()/nth()`。
- **解决方案**: 用**标准 CSS 结构定位**锁定唯一目标——通过父容器 + 结构伪类，如 `父容器 > 子:first-child`（`:first-child` / `:nth-child(n)` 属标准 CSS 伪类，是页面结构的一部分，**不是** Playwright 的 `.first()` 链式调用，符合 ai-selector 规则6）。
  - 正确：`{type: css, selector: ".promo_wrapper > .promo_package_option:first-child"}`，再 `verify_locator` 确认 `count==1`。
  - 错误：`page.locator(".promo_package_option").first()`（违反规则6，且脆弱）。
- **适用 agent**: selector-debug
- **最近验证日期**: 2026-06-09

## Playwright 立即型 API（is_visible/is_enabled/is_checked）不接 timeout 参数
- **问题域**: PlaywrightAPI用法
- **症状**: 给 `Locator.is_visible()` / `is_enabled()` / `is_checked()` 传 `timeout` 参数（如 `is_visible(timeout=500)`）不生效——这些是**立即返回型** API，不等待元素出现；部分版本对该参数**静默忽略、不报错**，极易漏看，误以为「带了等待」实则当下就判定。
- **根因**: Playwright Python 把 `is_*` 系列设计为「即时状态查询」，不接受 timeout；真正带等待语义的是 `wait_for` / `expect`。
- **解决方案**:
  - 仅做**即时判断** → 用无参 `locator.is_visible()` / `is_enabled()` / `is_checked()`。
  - 需要**等待**元素出现 / 可见再判断 → 用 `locator.wait_for(state="visible", timeout=...)` 或 `expect(locator).to_be_visible(timeout=...)`。
- **出处**: `conftest.py` teardown 曾误写 `is_visible(timeout=500)`，本会话已改为 `is_visible()`。
- **适用 agent**: selector-debug / gio-tracking / code-engineer
- **最近验证日期**: 2026-06-16
