# Account Pool（账号池使用约定）

## 用途

给 **模型** 在 `case-to-code` 生成新自动化用例时使用：根据用例对账号的需求标签，从 `tests/data/account_pool.yaml` 挑出最合适的账号，把它的 `username / password` 写进新生成的 `tests/data/<feature>_data.yaml`。

**不是运行时机制**：conftest / fixture / Page 类 / test 代码完全不读账号池。

## 触发场景

- `case-to-code` 工作流 Step 4.5（账号解析阶段）
- 用户口头要求："给这个新用例挑个合适的账号"
- 用户口头要求："池子里有没有 vip + has_orders 的账号"

## 池子数据 schema

文件位置：`tests/data/account_pool.yaml`

```yaml
accounts:
  - username: "..."           # 必填
    password: "..."           # 必填
    tags: [..., ...]          # 必填，至少 1 个 snake_case 标签
    description: "..."        # 必填，一句话人类可读说明
    added_at: "YYYY-MM-DD"    # 可选，纯审计
    added_for: "..."          # 可选，纯审计
```

## 标签命名约定（强约束）

新增账号前必须先 `grep` 已有标签，能复用就复用，避免同义异写。

| 类别 | 命名规则 | 示例 |
|------|---------|------|
| 业务能力 | `<功能>_<动作>` 或 `<功能>er` | `pin_image_downloader`, `atm_renderer`, `workflow_creator` |
| 状态/数据 | `<状态>` 或 `<状态>_<数量>` | `has_orders`, `empty_cart`, `no_permission`, `image_download_100x` |
| 角色身份 | 单词 | `vip`, `free_tier`, `admin` |
| 通用兜底 | `default`, `generic_user` | "任何登录态都行"时使用 |

**严格 AND 字符串匹配**：`vip` ≠ `VIP` ≠ `is_vip`。新增前先查已有标签：

```bash
grep -h "      -" tests/data/account_pool.yaml | sort -u
```

## 匹配算法（模型必须严格执行）

输入：用例需求标签数组 `required_tags`（例 `[vip, has_orders]`）

```
1. 过滤（严格 AND）：保留 account.tags 是 required_tags 超集的账号
   即：required_tags 中每个标签都必须出现在 account.tags 中

2. 排名（最小超集优先）：候选集按 len(account.tags) 升序

3. 并列时（同 tags 长度）：按 added_at 升序；缺失 added_at 则按 yaml 中出现顺序

4. 截断：取 top 3

5. 决策：
   - 0 个候选 → 停下，告诉用户：
       "池子里没有满足 tags=[xxx] 的账号，
        请在 tests/data/account_pool.yaml 追加一条 tags=[xxx, ...] 的账号，
        然后告诉我继续。"
       不要自作主张挑近似的。
   - 1 个候选 → 直接用，一行通知：
       "✓ 使用账号 <username>（tags=[...]）"
   - 2~3 个候选 → 调用 AskUserQuestion，每个选项展示：
       · username（明文）
       · tags 完整列表
       · description
     让用户选。
```

## 特殊默认路径（无需匹配，直接走默认账号）

当用例 Markdown 的「前置条件」**未明确**账号需求（如只写"已登录"/"已进入系统"/"账号已登录"等通用表述），跳过匹配，直接：

1. 把需求标签定为 `[generic_user]`
2. 不调用 AskUserQuestion
3. 直接使用池子里 `tags` 包含 `default` 和 `generic_user` 的账号（当前是 `17768100279`）

此路径设计用途：避免模型对每个"通用登录态"用例都打断用户。

## 拿到账号后做什么

把选中账号的 `username` 和 `password` **写入** `tests/data/<feature>_data.yaml` 根级：

```yaml
# tests/data/<feature>_data.yaml
username: "13060613380"
password: "Qyff2011"
# 其他业务数据...
cases: []
```

测试用例代码沿用现有模式从 `_DATA["username"]` 读取，**不感知账号池**。

## 新增账号工作流（用户/模型协作）

当模型遇到 0 候选场景，告知用户后由用户主导追加：

1. 用户决定用哪个真实账号，告知模型 username + password
2. 用户告知模型这个账号的业务特性（一句话）
3. 模型负责把这条 entry 追加到 `tests/data/account_pool.yaml`：
   - 按标签命名约定挑标签（业务能力 / 状态 / 角色，能复用优先）
   - 填 description（用户告知的一句话）
   - 可填 added_at（当前日期）+ added_for（首次为哪条用例登记）
4. 模型把追加内容给用户确认
5. 用户确认 → 模型继续 case-to-code 流程

## 输出示例

### 场景 A：1 候选直接用
```
✓ 使用账号 17768100279（tags=[default, generic_user]）
  来源：池子里唯一满足 [generic_user] 的账号
```

### 场景 B：2~3 候选询问
```
AskUserQuestion:
  Q: 池子里有 2 个账号满足 tags=[vip]，选哪个？
  Options:
    A. 18800000001
       tags: [vip]
       desc: 纯 VIP 账号，无业务状态
    B. 18800000002
       tags: [vip, has_orders, image_download_100x]
       desc: VIP + 已有订单 + 已下载过 100 次的复合账号
```

### 场景 C：0 候选停下
```
✗ 池子里没有满足 tags=[vip, has_orders] 的账号。
  请在 tests/data/account_pool.yaml 追加一条这种账号，
  告诉我用户名密码后我帮你写入。
  暂停后续 case-to-code 流程。
```

## 不做的事

- ❌ 运行时读账号池（不引入 fixture、marker、AccountPool.get() 工具类）
- ❌ 跨账号池跨标签的语义/模糊匹配（embedding、近义词）
- ❌ 账号状态机 / 并发锁 / xdist 隔离
- ❌ 加密存储（明文与现有 login_data.yaml 等同安全等级）
- ❌ 自动注册新账号 / 自动检测账号失效
- ❌ 修改 `tests/data/login_data.yaml` 的格式或 conftest 读取逻辑（仅可加注释）
