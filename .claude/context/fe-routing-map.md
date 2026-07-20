# zhimo_web2.0 路由映射

> 适用项目：zhimo_web2.0（知末主站 + 各子站）
> 最后更新：2026-07-03
> 来源：`routes/zhimo.js`（核心）、`routes/personCenter.js`、`routes/staticHtml.js`、`routes/reptile.js`

---

## 辅助路由（Express Router 挂载）

| 挂载路径 | 文件 | 用途 |
|---|---|---|
| `/personalCenter` | `routes/personCenter.js` | 伺服旧版静态 HTML 个人中心页 |
| `/webH5` | `routes/staticHtml.js` | 伺服 H5 静态页 |
| 根级 | `routes/reptile.js` | `/robots.txt`（按域名分发）、`/*.xml` Sitemap |

---

## 首页

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `GET /`（`www.znzmo.com`） | `/mainhome` | 知末主站首页 |
| `GET /`（`3d.znzmo.com` / `su.znzmo.com`） | `/threedSuLanmuChangeHome` | 3D/SU 子域首页 |
| `GET /`（`haoke.znzmo.com`） | `/educationHome` | 好课教育首页 |
| `GET /3d` / `/su` / `/tietu` / `/sgt` / `/wenben` | `/3dHome` / `/suNewHome` / `/tietuHome` / `/cadNewHome` / `/wenbenHome` | 各频道首页 |

## 详情页

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `/(3dmoxing\|sumoxing\|tietu\|caizhi\|...)/数字.html` | `/detail` | 通用素材详情页 |
| `/sgt/数字.html` | `/detail` | CAD 图纸详情（仅 `sgt.znzmo.com`） |
| `/xgt/数字.html` | `/xiaoguotuDetail` | 效果图详情 |
| `/ke/数字.html` | `/educationDetail` | 教育课程详情 |

## 列表 / 搜索页

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `/3dmoxing***.html` / `/sumoxing***.html` | `/threedSuLanmu` | 3D/SU 模型列表页 |
| `/cgmoxing***.html` / `/qjmx***.html` | `/newLanmu` | CG 模型/全景列表页 |
| `/sgt***.html` / `/tietu***.html` / `/caizhi***.html` | `/tietuCadLanmu` | 贴图/CAD/材质列表页 |
| `/wenben***.html` | `/wenbenLanmu` | 文本方案列表页 |
| `/xgt***.html` | `/xiaoguotuLanmu` | 效果图列表页 |
| `/general***.html` | `/generalLanmu` | 通用综合搜索结果页 |

## AI 绘图（仅限 `ai.znzmo.cn`）

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `/community/AIDrawPage.html` | `/AIDrawPage` | AI 绘图主页 |
| `/AIDrawEdit` | `/AIDrawEdit` | AI 改图页 |
| `/AIDrawPlugin` | `/AIDrawPlugin` | AI 绘图插件页 |
| `/infiniteCanvas` | `/AIDrawInfiniteCanvasV3` | 无限画布 V3（当前使用版） |
| `/infiniteCanvasV1` | `/AIDrawInfiniteCanvas` | 无限画布 V1（旧版） |
| `/AIDrawNewHome.html` | `/AIDrawNewHome` | AI 绘图新首页 |
| `/AIDrawRednoteActivity.html` | `/AIDrawRednoteActivity` | AI 绘图小红书活动页 |

## AI 聊天（仅限 `ai.znzmo.cn`）

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `/chat` | `/chat` | 知末 AI 助手主页 |
| `/chat/c/:chatId` | `/chat/c/[chatId]` | AI 聊天具体会话页 |
| `/chat/draw` | `/chat/draw` | AI 聊天生图页 |
| `/chat/search` | `/chat/search` | AI 搜索初始化页 |
| `/chat/project/:projectId` | `/chat/project/[projectId]` | AI 项目主页 |

## 用户中心 / 会员

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `/user_privilege.html` | `/userPrivilege` | VIP 特权详情页 |
| `/vipZone.html` | `/newVipZone` | VIP 专区 |
| `/collectPage.html` | `/collectPage` | 收藏页 |
| `/myprojects.html` | `/myprojects` | 我的项目 |

## 其他功能

| URL 规则 | Pages 文件 | 说明 |
|---|---|---|
| `/(register\|login).html` | `/login` | 登录/注册页 |
| `/auth.html` | `/auth` | OAuth 授权回调页 |
| `/subpages/*.html` | `/subpages` | 协议/说明子页面 |
| `/kefuChat.html` | `/kefuChat` | AI 客服对话 |

---

## 仅通过 Next.js 自动路由（未在 `zhimo.js` 显式注册）

| Pages 目录 | 说明 |
|---|---|
| `/userCenter` | 用户中心（资产与订单） |
| `/creatorCenter` | 创作者中心 |
| `/toolbox/[type]` | AI 工具箱 |
| `/thirdPartyLogin` | 第三方登录 |
| `/search/floorplan` | 户型图搜索页 |

---

## 域名与 pages 速查

| 域名 | 主要对应 pages |
|---|---|
| `www.znzmo.com` | `mainhome`、`detail`、`threedSuLanmu` |
| `3d.znzmo.com` | `threedSuLanmuChangeHome`、`threedSuLanmu`、`newLanmu`、`3dHome` |
| `su.znzmo.com` | `threedSuLanmuChangeHome`、`threedSuLanmu`、`suCategory`、`suNewHome` |
| `sgt.znzmo.com` | `cadNewHome`、`tietuCadLanmu`、`detail` |
| `ai.znzmo.cn` | 全部 AI 绘图页、全部 chat 页 |
| `www.znztool.com` | `software`、`software_detail`、`software_list` |
