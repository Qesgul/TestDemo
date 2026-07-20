# AI 绘图弹窗优先级上下文

> 适用项目：zhimo_web2.0（ai.znzmo.cn）
> 最后更新：2026-07-03

## 必读文件

| 文件 | 说明 |
|---|---|
| `components/AIDrawPopupManager/index.tsx` | 定义 `POPUP_QUEUE`，数组下标即优先级，`0` 最高 |
| `zustandStore/useAIDrawPopupPriorityStore.ts` | 令牌链状态管理（currentPriority/start/next/reset） |
| `components/AIDrawPopupManager/types.ts` | `PopupWrapperProps` 接口定义 |

## 令牌链机制

```
登录或场景切换
  -> reset()
  -> start()
  -> priority 0 Wrapper 检查
      -> 命中：展示并持有令牌
      -> 不命中：next(0)
          -> priority 1 Wrapper 检查
              -> 依次类推
```

## 标准 Wrapper 形态

```tsx
const XxxWrapper: React.FC<PopupWrapperProps> = ({ priority }) => {
  const { currentPriority, next } = useAIDrawPopupPriorityStore();
  const isMyTurn = currentPriority === priority;

  useEffect(() => {
    if (!isMyTurn) return;
    if (shouldNotShow) {
      next(priority);
      return;
    }
    // 命中时展示弹窗并持有令牌
  }, [isMyTurn, next, priority]);

  return isMyTurn && visible ? <Modal /> : null;
};
```

## 当前真实优先级顺序（以代码为准）

| index | Wrapper | 触发页面/条件 |
|---|---|---|
| 0 | `InfiniteCanvasGuideWrapper` | `/community/AIDrawPage.html`，接口判定 |
| 1 | `HomeVoteWidgetWrapper` | `/community/AIDrawPage.html` + `isAiDrawHome` + 已登录 + 接口判定 |
| 2 | `InfiniteCanvasSurveyWrapper` | `/infiniteCanvas?canvasId=xxx` 且非 `readonly`，仅画布详情页 |
| 3 | `AIDrawCanvasGiftWrapper` | `/infiniteCanvas` 详情页或画布首页；画布页会占住令牌 |
| 4 | `BananaLandpageWrapper` | `AIDrawPage` + `utm_source=gude` + `menuKey=agent` |
| 5 | `PluginActivationWrapper` | `/community/AIDrawPage.html` |
| 6 | `NewUserTaskV2Wrapper` | `/community/AIDrawPage.html`，切量组 = 1 |
| 7 | `BananaRemindWrapper` | `/AIDrawPage` / `/AIDrawEdit` / `/infiniteCanvas` |
| 8 | `BananaGuideWrapper` | `/AIDrawPage` / `/AIDrawEdit` |
| 9 | `BananaNewUserWrapper` | `/AIDrawPage` / `/AIDrawEdit` |
| 10 | `NewUserTaskWrapper` | `ai.znzmo.cn`，切量组 ≠ 1 |
| 11 | `NewUserRetentionWrapper` | `ai.znzmo.cn`，切量组 ≠ 1 |
| 12 | `RednoteActivityWrapper` | `/AIDrawPage` + `isAiDrawHome` |
| 13 | `NewEditWrapper` | `/AIDrawEdit` |
| 14 | `DesignFieldWrapper` | `/AIDrawPage` + `isAiDrawHome`，切量组 ≠ 1 |
| 15 | `FeatureRecomendationWrapper` | `/AIDrawPage` |
| 16 | `ProductExamWrapper` | `/community/AIDrawPage.html?menuKey=home`，问卷开关接口 |
| 17 | `AdForPluginWrapper` | `/AIDrawPage` + `isAiDrawHome` |
| 18 | `SvipNoticeWrapper` | `/community/AIDrawPage.html` + `isAiDrawHome`，每用户仅一次，组 ≠ 1 |
| 19 | `Sale3rdWrapper` | `/community/AIDrawPage.html` + `isAiDrawHome`，累计 < 2 次 |

## 操作规则

1. **调整优先级**：只改 `POPUP_QUEUE` 顺序，不改各个 Wrapper 内部优先级常量
2. **新增弹窗**：按 `XxxWrapper` → `import` → 插入 `POPUP_QUEUE` 的顺序处理
3. **容器自动注入**：`priority={index}` 由容器自动注入给每个 Wrapper
4. **强制同步**：任务结束前必须重新读取真实 `index.tsx`，按真实 `POPUP_QUEUE` 重建优先级表
5. **不一致时**：只同步本卡片，不顺手改业务代码来"迎合卡片"
