# 项目内部 Hooks

## Section A — 滚动 / DOM 位置检测（行 3-80）

### useScrollJudgePosition
文件：`util/hooks/useScrollJudgePosition.ts`
场景：监听页面/容器滚动方向（上/下），内置防抖，替代手写 scroll 事件。

```ts
import useScrollJudgePosition from '@/util/hooks/useScrollJudgePosition';

const [scrollStatus] = useScrollJudgePosition({
  target?: HTMLElement | null, // null 时自动用 window / #interiorContent
  toTop?: () => void,
  toBottom?: () => void,
  wait?: number,          // 防抖 ms，默认 10
  defaultStatus?: 'top' | 'bottom', // 默认 'top'
  startScroll?: number,   // 最小触发滚动距离，默认 0
});
// scrollStatus: 'top' | 'bottom'
```

---

### useScrollStop
文件：`util/hooks/useScrollStop.ts`
场景：滚动完全停止后才触发回调（防抖封装），同时返回 isScrolling 状态。

```ts
import { useScrollStop } from '@/util/hooks/useScrollStop';

const { isScrolling } = useScrollStop(
  target,   // HTMLElement | null
  callback, // 停止时调用
  500,      // wait ms，默认 500
);
```

---

### useMainScrollTarget / useMainScrollListener / getMainScrollScrollTop
文件：`util/hooks/useMainScrollTarget.ts`
场景：主站滚动容器是 window 或 `#interiorContent`，统一读取/绑定，不要手写 `window.addEventListener('scroll')`。

```ts
import {
  useMainScrollTarget,    // 组件内：返回当前主滚动容器
  useMainScrollListener,  // 组件内：绑定 scroll 事件，全站布局挂载后自动换绑
  getMainScrollScrollTop, // 非 hook 上下文：获取当前主滚动距离
} from '@/util/hooks/useMainScrollTarget';

const target = useMainScrollTarget(); // Window | HTMLElement | null
useMainScrollListener((e) => { /* ... */ }, { enable: true });
const scrollTop = getMainScrollScrollTop(); // number
```

---

### useEleInViewport
文件：`util/hooks/useEleInViewport.ts`
场景：IntersectionObserver 封装，元素是否在视口内。

```ts
import { useEleInViewport } from '@/util/hooks/useEleInViewport';

const ref = useRef<HTMLElement>(null);
const inViewport = useEleInViewport(ref); // boolean
```

---

### useDomToView
文件：`util/hooks/useDomToView.ts`
场景：同时需要「在视口」判断 + 「滚动到元素」的场景。

```ts
import { useDomToView } from '@/util/hooks/useDomToView';

const ref = useRef<HTMLDivElement>(null);
const { inViewport, scrollIntoView } = useDomToView(ref);
scrollIntoView(); // 默认 smooth + center
```

## Section B — UI 交互（行 82-136）

### useAddMask
文件：`util/hooks/useAddMask.ts`
场景：创建全屏透明遮罩层（阻止鼠标穿透，如自定义下拉打开时）。

```ts
import { useAddMask } from '@/util/hooks/useAddMask';

const { openMask, closeMask } = useAddMask({ id: 'myMask', zIndex: 1000 });
// openMask() / closeMask() 控制遮罩显示
```

---

### useHoverTime
文件：`util/hooks/useHoverTime.ts`
场景：鼠标悬停超过指定时长后触发回调（如悬停 3s 展示详情卡片）。

```ts
import { useHoverTime } from '@/util/hooks/useHoverTime';

const ref = useRef<HTMLElement>(null);
const [isOverTime, clear] = useHoverTime(ref, 3000, () => {
  // 悬停超过 3s 执行
});
// clear() 手动取消计时
```

---

### useMouseTripleClick
文件：`util/hooks/useMouseTripleClick.ts`
场景：捕获元素上的三连击，返回三次点击坐标。

```ts
import { useMouseTripleClick } from '@/util/hooks/useMouseTripleClick';

const ref = useRef<HTMLElement>(null);
const [positions] = useMouseTripleClick(ref);
// positions: [{x, y}, {x, y}, {x, y}]
```

---

### useElementOpen
文件：`util/hooks/useElementOpen.ts`
场景：展开/收起动画所需的真实高度（替代写死 max-height）。

```ts
import useElementOpen from '@/util/hooks/useElementOpen';

useElementOpen(ref.current, isOpen, (height) => {
  setMaxHeight(height ? `${height}px` : '0px');
});
```

## Section C — 数据获取 / 文件上传（行 138-185）

### useCachedHoverFetch
文件：`hooks/useCachedHoverFetch.ts`，从 `@/hooks` 导入
场景：鼠标悬停后触发 fetch，内置防抖（300ms）和内存缓存（30min），适合卡片 hover 预加载。

```ts
import { useCachedHoverFetch } from '@/hooks';

const { data, isLoading, onMouseEnter, onMouseLeave } = useCachedHoverFetch({
  cacheKey: item.id,
  fetcher: () => fetchDetail(item.id),
  enabled: true,             // 可用于条件控制
  delay: 300,                // 悬停防抖 ms
  cacheExpireTime: 30 * 60 * 1000,
});
// <div onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
```

---

### useFileUpload（通用多文件上传，队列管理）
文件：`hooks/useFileUpload.ts`，从 `@/hooks` 导入
场景：多文件 OSS 上传，有状态列表（uploading/success/error）管理。

```ts
import { useFileUpload, type UseFileUploadReturn } from '@/hooks';
// 返回 { fileUploadStatus, setFileUploadStatus, ... }
```

---

### useFileUpload（AI 绘图单文件上传 + 校验）
文件：`util/hooks/useFileUpload.ts`，从 `@/util/hooks/useFileUpload` 导入
场景：AI 绘图参考图上传，含格式/大小/分辨率/宽高比校验 + OSS 上传 + 校验接口。

```ts
import { useFileUpload } from '@/util/hooks/useFileUpload';

const { uploading, fileInputRef, handleFileChange, triggerFileSelect } = useFileUpload({
  ossToken,                            // 必需
  acceptTypes?: ['image/png', ...],    // 默认 png/jpg/jpeg
  maxSize?: 10,                        // MB
  minResolution?: 512,
  onSuccess: (url) => {},
  onError: (err) => {},
});
```

## Section D — 动画 / 布局（行 187-249）

### useParabolicAnimation
文件：`hooks/useParabolicAnimation.ts`，从 `@/hooks` 导入
场景：从起点飞到终点的抛物线动画（购物车效果）。

```ts
import { useParabolicAnimation } from '@/hooks';

const triggerAnimation = useParabolicAnimation();

// 在点击事件中调用
const targetEl = document.getElementById('upload-list');
triggerAnimation(e.currentTarget as HTMLElement, targetEl, {
  duration: 800,            // 动画时长 ms
  curvature: -200,          // 弧度（负数向上）
  elementContent: imageUrl, // 图片 URL 或省略（默认蓝色圆点）
  onComplete: () => {},
});
```

---

### useMasonry
文件：`hooks/useMasonry.ts`，从 `@/hooks/useMasonry` 导入
场景：瀑布流布局（masonry-layout 封装），依赖变化自动重布局，内置图片加载监听。

```ts
import { useMasonry } from '@/hooks/useMasonry';

const { masonryRef, triggerLayout, relayoutMasonry } = useMasonry(
  [listData],    // 依赖数组（数据变化时重布局）
  {
    columnWidth: 264,
    gutter: 20,
    fitWidth: true,
    enableImageLoader: true,
  }
);
// <div ref={masonryRef}>
//   {items.map(i => <div className="masonry-item" key={i.id}>...</div>)}
// </div>
// 图片加载完后调用 relayoutMasonry()
```

---

### useResizableDrag
文件：`hooks/useResizableDrag.ts`，从 `@/hooks` 导入
场景：拖拽调整面板宽度（侧边栏 resize 手柄），双击复位，支持宽度范围限制。

```ts
import { useResizableDrag } from '@/hooks';

const { width, isDragging, handleMouseDown, handleDoubleClick } = useResizableDrag({
  defaultWidth: 540,
  minWidth: 300,
  maxWidth: 1000,
  onDragEnd: (w) => saveToStorage(w),
});
// <div style={{ width }}>
//   <div onMouseDown={handleMouseDown} onDoubleClick={handleDoubleClick} />
// </div>
```

## Section E — URL / Router（行 251-299）

### URL Query 工具函数
文件：`util/hooks/urlQueryFromSearch.ts`
场景：SSR 安全的 URL query 解析/序列化/替换，兼容 history.replaceState（AIDrawPage 等非 Next.js 路由页）。

```ts
import {
  searchToParsedQuery,          // search → ParsedUrlQuery
  parsedQueryToSearchString,    // ParsedUrlQuery → '?a=1&b=2'
  replaceBrowserLocationQuery,  // 无感替换当前页 search（自动触发 popstate）
} from '@/util/hooks/urlQueryFromSearch';

const query = searchToParsedQuery(window.location.search);
replaceBrowserLocationQuery(nextQuery);
```

---

### useRemoveParamOnChange
文件：`util/hooks/useRemoveParamOnChange.ts`
场景：watchKey 变化时自动移除 URL 中的 removeKey（首屏不触发，只响应后续变化）。

```ts
import { useRemoveParamOnChange } from '@/util/hooks/useRemoveParamOnChange';

useRemoveParamOnChange({
  watchKey: 'tab',       // 监听此参数的变化
  removeKey: 'popup',    // 变化时移除此参数
  shallow: true,
  watchSource: 'router', // 或 'location'（AIDrawPage 等 replaceState 场景）
});
```

---

### useRemoveQueryOnReload
文件：`util/hooks/useRemoveQueryOnReload.ts`
场景：整页刷新（F5）后从 URL 移除指定参数（默认读 window.location，与 AIDrawPage 一致）。

```ts
import { useRemoveQueryOnReload } from '@/util/hooks/useRemoveQueryOnReload';

useRemoveQueryOnReload({
  paramKeys: ['popup', 'taskGuide'],
  shouldRemove: () => !isLoading,
  watchSource: 'location',
});
```

## Section F — 登录态（行 301-314）

### useAuth
文件：`hooks/auth/useAuth.ts`
场景：订阅全站登录态，不触发请求（由 AuthBootstrap/_app 统一发起）。任何需要 userInfo/loginEnd 的组件都可用。

```ts
import useAuth from '@/hooks/auth/useAuth';

const { userInfo, loginEnd, isAuthLoading, authError, refresh } = useAuth();
// userInfo: {} 未登录 | { accountId, ... } 已登录
// loginEnd: boolean（登录流程完成才为 true）
// refresh() 重置单例，下次重新发请求
```
