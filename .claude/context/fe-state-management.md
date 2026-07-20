# 全局状态注入 / 声明指南

> 适用项目：zhimo_web2.0
> 最后更新：2026-07-03
> 本项目并存 **Redux**（遗留类组件）和 **Zustand**（新功能函数组件）两套状态体系。

## 判断用哪套体系

| 场景 | 应该用 |
|------|--------|
| 修改/维护已有类组件（`class Xxx extends Component`） | Redux connect |
| 新功能、新函数组件、重构 | Zustand hook |
| 新增全局状态 | **只用 Zustand**，禁止新增 Redux action/reducer |

---

## Redux —— 类组件读取 / 注入全局变量

### 读取已有 Redux 状态（mapStateToProps）

所有可读状态字段定义在 `store/reducers.js` 的 `InitialState` 对象里。

```js
const mapStateToProps = (state) => {
  const { userInfo, loginEnd, isOpenLoginModal } = state;
  return { userInfo, loginEnd, isOpenLoginModal };
};
const mapDispatchToProps = (dispatch) => ({ dispatch });
export default connect(mapStateToProps, mapDispatchToProps)(MyComponent);
```

### 触发已有 Redux action（dispatch）

action 函数定义在 `store/actions.js`，action 类型常量在 `store/action-types.js`。

```js
import { setLoginModal, loginFn } from '@/store/actions';
const { dispatch } = this.props;
setLoginModal(dispatch, true);
```

### 在 Redux 里新增字段（仅维护遗留代码时）

> ⚠️ 新功能禁止走这条路，请用 Zustand。

需要改三个文件：
1. `store/action-types.js` — 添加类型常量
2. `store/reducers.js` — 在 `InitialState` 添加初始值，在 `switch` 里添加 `case`
3. `store/actions.js` — 添加 action 函数

---

## Zustand —— 函数组件读取 / 注入全局变量

### 常用 Zustand store

| store 文件 | 包含内容 |
|-----------|---------|
| `useAuthStore.ts` | `userInfo`、`loginEnd`、`isAuthLoading` |
| `useModalStore.js` | VIP弹窗、充值弹窗、AI绘图弹窗等 `visible` 状态 |
| `useUserGroupStore.js` | 所有切量 groupValue |
| `useHeaderStore.js` | Header 相关状态 |
| `useSystemStore.ts` | 系统级标志（webp支持、窗口加载等） |

### 读取已有 Zustand store

```ts
import useAuthStore from '@/zustandStore/useAuthStore';
const { userInfo, loginEnd } = useAuthStore();

// 推荐：按需取值，避免无关更新触发重渲染
const userInfo = useAuthStore((s) => s.userInfo);
```

### 在已有 store 里新增字段

```js
const useModalStore = create((set) => ({
  // 已有状态...
  myNewModalVisible: false,
  setMyNewModalVisible: (visible) => set({ myNewModalVisible: visible }),
}));
```

### 新建 Zustand store（新业务域）

在 `zustandStore/` 下新建文件，单文件即可：

```ts
import { create } from 'zustand';
type XxxState = { loading: boolean; data: SomeType | null; setLoading: (v: boolean) => void; setData: (v: SomeType) => void; };
const useXxxStore = create<XxxState>((set) => ({ loading: false, data: null, setLoading: (loading) => set({ loading }), setData: (data) => set({ data }) }));
export default useXxxStore;
```

---

## 常见跨组件传递场景速查

| 场景 | 做法 |
|---|---|
| 函数组件里需要 `dispatch`（调用 Redux action） | `useDispatch()` hook |
| 函数组件里读取 Redux state | `useSelector((state) => state.xxx)` |
| 类组件里调用 Zustand store 的方法 | `useXxxStore.getState().method()` |

---

## 禁止事项

- 禁止新增 Redux 的 action-types / actions / reducers 三层模板（新状态一律 Zustand）
- 禁止在 `mapStateToProps` 里返回整个 `state`（性能问题）
- 禁止在函数组件里 `import store from '@/store/store'` 然后 `store.getState()` 手动读 Redux
