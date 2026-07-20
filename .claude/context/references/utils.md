# 项目工具函数

## Section A — URL 工具 (util/url.ts)（行 3-68）

### updateUrlParam
场景：无感更新地址栏单个参数（history.replaceState 封装）。

```ts
import { updateUrlParam } from '@/util/url';

updateUrlParam('tab', 'design');            // 更新当前页 URL
updateUrlParam('tab', 'design', otherUrl);  // 更新指定 URL（不改地址栏，返回新 URL 字符串）
```

---

### getLinkMediaType
场景：从 URL 判断链接类型（视频/图片），替代手写扩展名正则。

```ts
import { getLinkMediaType } from '@/util/url';

const type = getLinkMediaType(url); // 'video' | 'image' | null
```

---

### getTaskGuideFromUrl
场景：从 search 或 hash 中读取参数（兼容 hash 路由页面）。

```ts
import { getTaskGuideFromUrl } from '@/util/url';

const value = getTaskGuideFromUrl('taskGuide'); // string（不存在返回 ''）
```

---

### removeUrlSearchParam
场景：从当前页 search 中移除单个参数，保留其余 query，自动触发 popstate。

```ts
import { removeUrlSearchParam } from '@/util/url';

removeUrlSearchParam('popup');
```

---

### clearUrlParamsKeepMenuKey
场景：清除地址栏所有参数，仅保留 menuKey，自动触发 popstate。

```ts
import { clearUrlParamsKeepMenuKey } from '@/util/url';

clearUrlParamsKeepMenuKey();
```

---

### isAgentSiteAutoTaskGuideUrl
场景：判断当前 URL 是否为 AI 智能体自动任务引导链接（含 agentAutoTaskId + agentAutoTaskType）。

```ts
import { isAgentSiteAutoTaskGuideUrl } from '@/util/url';

const result = isAgentSiteAutoTaskGuideUrl(); // { taskId, taskType } | undefined
```

## Section B — Cookie 工具 (util/cookieUtil.ts)（行 70-92）

### setCookie / setCookieSecond / getCookieDomain
场景：写 cookie 时先用 getCookieDomain() 获取当前 host 对应的 domain，再调 setCookie。

```ts
import { setCookie, setCookieSecond, getCookieDomain } from '@/util/cookieUtil';

const domain = getCookieDomain(); // 自动推导当前 host 的 cookie domain
setCookie('myKey', 'value', 7, domain);          // 7 天
setCookieSecond('myKey', 'value', 3600, domain); // 1 小时
```

---

### getCookie
场景：读取 cookie。

```ts
import { getCookie } from '@/util/cookieUtil';

const value = getCookie('myKey'); // string（不存在返回 ''）
```

## Section C — 弹窗工具（行 94-118）

### openLoginModal / closeLoginModal
文件：`util/openLoginModal.ts`
场景：打开/关闭登录弹窗，全站统一入口（底层走 Redux，迁移到 zustand 时只改此文件）。

```ts
import { openLoginModal, closeLoginModal } from '@/util/openLoginModal';

openLoginModal({ redirect: '/target' }); // 可传任意参（由 LoginModal 消费）
closeLoginModal();
```

---

### modalBlockingCondition
文件：`util/modalBlockingCondition.ts`
场景：判断当前场景是否需要阻塞全局优先级弹窗（有任务引导、特定来源用户、自动任务等情况返回 true）。

```ts
import modalBlockingCondition from '@/util/modalBlockingCondition';

const blocked = modalBlockingCondition(userInfo); // boolean
// true → 不弹此次弹窗
```

## Section D — GIO 埋点工具（行 120-155）

> **规则：新增非切量埋点（用户行为事件、点击、曝光等）一律使用 `safeTrack`，禁止直接调用 `gio(...)`。**
> 切量分组上报使用 `trackGroupMapping` / `batchTrackGroupMapping`（见下）。

### safeTrack（非切量埋点唯一入口）
文件：`util/gioUtils/index.ts`
场景：新增用户行为埋点时的唯一合法方式。内部 try/catch，埋点错误不影响主流程，不需要调用方手写容错。

```ts
import { safeTrack } from '@/util/gioUtils';

// safeTrack(event, eventId, data?)
// event 通常固定为 'track'
safeTrack('track', 'button_click', { page: 'home', type: 'cta' });
safeTrack('track', 'page_view');

// ❌ 禁止直接调用 gio()，没有容错保护
// gio('track', 'button_click', { ... });
```

---

### trackGroupMapping / batchTrackGroupMapping（仅用于切量分组上报）
文件：`util/gioUtils/gioTracking.ts`
场景：切量 AB 分组 → GIO 维度上报。新增切量在 GROUP_TRACKING_LIST 追加条目，batchTrackGroupMapping 自动覆盖。

```ts
import { trackGroupMapping, batchTrackGroupMapping } from '@/util/gioUtils/gioTracking';

// 单条上报（已知分组值 + trackingKey）
trackGroupMapping(groupValue, 'aiDiversionV2', '0');

// 批量上报（useTracking.ts 统一调用，通常不需要手动调）
batchTrackGroupMapping(deviceGroupList, accountGroupList, stateSetters);
```

## Section E — 用户状态判断 (util/auth/userPredicates.ts)（行 148-168）

### isNewUser
场景：判断用户是否为新用户（注册 < 7 天）。

```ts
import { isNewUser } from '@/util/auth/userPredicates';

const newUser = isNewUser(userInfo); // boolean
```

---

### needAbnormalBehaviorPrevention
场景：当前页 pathname 是否需要走防代下行为（搜索结果页用）。

```ts
import { needAbnormalBehaviorPrevention } from '@/util/auth/userPredicates';

const need = needAbnormalBehaviorPrevention(); // boolean
```

## Section F — 数据格式化 (util/formatData.ts)（行 170-180）

### formatTrafficAdSlotData
场景：处理素材导流广告位数据（识别视频/图片类型、解析 param JSON、提取 isNew 标记）。

```ts
import { formatTrafficAdSlotData } from '@/util/formatData';

const slots = formatTrafficAdSlotData(rawData);
// 每项新增 effectType（1=视频 2=图片）、isNew（boolean）、param 展开字段
```

## Section G — 图标 (icons/IconFont)（行 182-200）

### IconFont
文件：`icons/IconFont/index.jsx`，从 `@/icons/IconFont` 导入
场景：**遇到字体图标，或识别设计稿中类似图标的图形，优先使用此组件**，不要用 emoji、原生字符、或引入第三方图标库。若项目图标库里确实没有，才考虑 `@ant-design/icons`。

```tsx
import IconFont from '@/icons/IconFont';

// type 值从 iconfont 项目（ID: 4471623）取，格式为 "icon-xxx"
<IconFont type="icon-guanbi" className={cs.closeIcon} onClick={onClose} />
<IconFont type="icon-tuikuanchenggong" style={{ fontSize: 20 }} />
```

图标资源：https://www.iconfont.cn/manage/index?manage_type=myprojects&projectId=4471623

## Section H — 本地存储 (util/storage.js)（行 199-220）

### setLocal / getLocal / removeLocal / setSession / getSession / removeSession
场景：读写 localStorage / sessionStorage，内置 SSR 安全（`window` 判断）和 JSON 序列化/反序列化，**替代直接调用 `localStorage.setItem` / `JSON.parse`**。

```ts
import {
  setLocal, getLocal, removeLocal,
  setSession, getSession, removeSession,
} from '@/util/storage';

// localStorage
setLocal('myKey', { a: 1 });       // 自动 JSON.stringify
const val = getLocal('myKey');     // 自动 JSON.parse，不存在返回 null
removeLocal('myKey');

// sessionStorage（用法相同）
setSession('token', 'abc');
const token = getSession('token');
removeSession('token');
```

注意：所有方法均对 `window === 'undefined'` 做了 SSR 保护，可在 Next.js 组件或 util 中直接使用。

## Section I — AI 绘图参数缓存 (util/aiDrawCache.js)（行 231-260）

### getAiDrawCache / saveAiDrawCache / clearAiDrawCache / getAllAiDrawCache / clearAllAiDrawCache
场景：AI 绘图页面的参数持久化缓存（localStorage，TTL 3 小时，key 前缀 `ai_draw_params_cache_`）。按 `pageKey` 区分不同页面的缓存。

```ts
import {
  getAiDrawCache,
  saveAiDrawCache,
  clearAiDrawCache,
  getAllAiDrawCache,
  clearAllAiDrawCache,
} from '@/util/aiDrawCache';

// 读取（过期自动返回 null）
const params = getAiDrawCache('home'); // data | null

// 写入
saveAiDrawCache('home', { style: 'modern', size: '1024' });

// 清除单页缓存
clearAiDrawCache('home');

// 读取所有页缓存（过滤已过期）
const all = getAllAiDrawCache(); // { home: {...}, edit: {...} }

// 清除所有 AI 绘图相关缓存
clearAllAiDrawCache();
```
