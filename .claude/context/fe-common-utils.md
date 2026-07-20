# 项目公共方法（Hooks + 工具函数）

> 适用项目：zhimo_web2.0
> 最后更新：2026-07-03
> 原则：项目已封装的公共方法优先使用，不要手写原生实现。

## 使用步骤

1. 从需求/代码中识别关键词，查下方映射表
2. 用 `Read` 工具加载对应文件的指定行（`offset` + `limit`）
3. 以读取内容为依据生成代码
4. 命中多条时合并 Read 调用（只读需要的）

参考文件根路径：`.claude/context/references/`

---

## 关键词 → 文件行号映射

### Hooks（references/hooks.md）

| 关键词（语义匹配） | offset | limit | 说明 |
|---|---|---|---|
| 滚动方向 scroll 上滚 下滚 滚动停止 主滚动容器 视口 IntersectionObserver DOM 位置 | 3 | 81 | Section A：滚动/DOM位置检测 |
| 遮罩 mask 悬停时长 hoverTime 三连击 展开高度 展开动画 useElementOpen | 84 | 57 | Section B：UI交互 |
| hover 预加载 悬停加载 缓存 fetch 文件上传 upload OSS 单文件上传 多文件上传 | 141 | 49 | Section C：数据获取/文件上传 |
| 抛物线动画 飞入动画 购物车动画 瀑布流 masonry 拖拽宽度 resize 可拖拽 | 190 | 65 | Section D：动画/布局 |
| URL 参数 query 路由清参 URLSearch replaceState 移除 URL 参数 刷新清参 | 255 | 50 | Section E：URL/Router |
| 登录态 userInfo loginEnd useAuth isAuthLoading | 305 | 15 | Section F：登录态 |

### 工具函数（references/utils.md）

| 关键词（语义匹配） | offset | limit | 说明 |
|---|---|---|---|
| updateUrlParam getLinkMediaType 判断链接类型 URL 工具 removeUrlSearchParam clearUrlParams | 3 | 67 | Section A：URL工具 |
| cookie setCookie getCookie getCookieDomain | 70 | 24 | Section B：Cookie工具 |
| 打开登录弹窗 openLoginModal closeLoginModal 弹窗阻塞 modalBlockingCondition | 94 | 26 | Section C：弹窗工具 |
| GIO 埋点 safeTrack 非切量埋点 用户行为埋点 点击埋点 曝光埋点 trackGroupMapping | 120 | 37 | Section D：GIO埋点工具 |
| isNewUser 新用户判断 needAbnormalBehaviorPrevention 防代下 | 148 | 22 | Section E：用户状态判断 |
| 广告位格式化 formatTrafficAdSlotData | 170 | 11 | Section F：数据格式化 |
| 图标 icon 字体图标 IconFont 设计稿图标 iconfont | 182 | 20 | Section G：图标 |
| localStorage sessionStorage 本地存储 setLocal getLocal storage | 198 | 25 | Section H：本地存储 |
| AI 绘图缓存 aiDrawCache getAiDrawCache saveAiDrawCache 参数缓存 | 231 | 32 | Section I：AI绘图参数缓存 |
