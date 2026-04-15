# Python + pytest + Playwright 自动化测试基础框架

## 技术栈
- Python
- pytest
- playwright（sync API）
- pyyaml
- allure-pytest
- pytest-xdist（并发执行）

## 目录结构
```text
.
├─common/                   # 基础共用方法（断言、通用工具）
│  ├─assertions.py          # 增强的断言诊断工具
│  ├─retry_utils.py         # 异常类型定向重试装饰器
│  └─wait_utils.py          # 智能等待工具类
├─config/                   # 配置
│  ├─settings.yaml          # 单文件多环境配置yaml
│  └─settings.py            # 统一配置管理模块（单例模式）
├─core/                     # 框架核心基类
│  ├─browser_manager.py     # Playwright 浏览器生命周期管理
│  ├─cookie_manager.py      # Cookie 管理器 - 支持快捷登录和环境隔离
│  └─base_page.py           # 基础页面类（POM基类）- 内置弹框处理
├─data_types/               # 数据类型定义（dataclass）
├─pages/
│  ├─elements/              # 页面元素定位（yaml）
│  └─methods/               # 页面方法（POM）
├─tests/
│  ├─cases/                 # 测试用例（已添加标签）
│  ├─data/                  # 测试数据（yaml）
│  └─steps/                 # 测试基础能力（test_base.py）
├─allure-results/           # Allure 测试结果数据
├─allure-report/            # Allure HTML 报告
├─conftest.py               # pytest fixture（浏览器/上下文/页面）
├─pytest.ini                # pytest 配置（已添加标记注册）
├─test_suite.yaml           # 测试套件配置（YAML 调度器）
├─run_suite.py              # 测试执行器（分组/标签执行）
└─requirements.txt
```

## 安装与初始化
```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器（必须步骤）
# 方式 1: 直接安装（可能比较慢）
python -m playwright install chromium

# 方式 2: 使用国内镜像加速（推荐）
# Windows:
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
python -m playwright install chromium

# Linux/Mac:
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ python -m playwright install chromium
```

### Allure 安装

**Windows (使用 Scoop)**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex
scoop install allure
```

**其他系统**
访问：https://docs.qameta.io/allure/

## 运行测试

### 方式1：YAML 调度器（推荐）

#### 列出可用分组和标签
```bash
python run_suite.py --list-groups
python run_suite.py --list-tags
```

#### 失败重试机制
本框架支持自动化失败重试功能，确保测试结果的可靠性。

##### 1. 配置文件配置 (test_suite.yaml)
```yaml
execution:
  retry:
    enabled: true           # 是否启用失败重试
    max_reruns: 2           # 最大重试次数（默认 2 次）
    reruns_delay: 1         # 重试间隔时间（秒）（默认 1 秒）
    only_flaky: false       # 是否仅对标记为 flaky 的用例重试
```

##### 2. 命令行参数
```bash
# 使用配置文件中的默认重试设置
python run_suite.py --group "快速检查"

# 自定义重试次数
python run_suite.py --group "核心功能" --reruns 3

# 自定义重试间隔
python run_suite.py --group "核心功能" --reruns 2 --reruns-delay 2

# 禁用重试功能
python run_suite.py --group "快速检查" --no-reruns

# 仅对标记为 @pytest.mark.flaky 的用例重试
python run_suite.py --group "弹框专项" --only-flaky

# 组合使用（并发 + 重试）
python run_suite.py --group "弹框专项" --parallel --workers 2 --reruns 1
```

##### 3. 为测试用例添加 flaky 标记
```python
import pytest

class TestMyFeature:
    @pytest.mark.flaky
    @pytest.mark.core
    def test_some_unstable_function(self):
        # 可能偶尔会失败的测试代码
        pass
```

#### 运行分组
```bash
# 运行默认分组（快速检查）
python run_suite.py

# 运行指定分组
python run_suite.py --group "快速检查"
python run_suite.py --group "核心功能"
python run_suite.py --group "弹框专项"
```

#### 运行标签
```bash
# 运行单个标签
python run_suite.py --tags quick
python run_suite.py --tags smoke

# 运行多个标签（OR 关系）
python run_suite.py --tags quick smoke
python run_suite.py --tags core ui
```

#### 报告选项
```bash
# 禁用 Allure 报告
python run_suite.py --group "快速检查" --no-allure

# 生成报告但不自动打开
python run_suite.py --group "快速检查" --no-open-report
```

### 方式2：直接使用 pytest
```bash
pytest
```

### 方式3：按标签运行 pytest
```bash
pytest -m quick
pytest -m "quick or smoke"
```

## 测试分组说明

| 分组名 | 标签 | 描述 |
|--------|------|------|
| 快速检查 | quick, smoke | 快速验证关键功能 |
| 核心功能 | core, main | 运行核心业务功能测试 |
| 弹框专项 | popup, ui | 弹框相关所有测试 |

## 测试标签说明

| 标签名 | 描述 |
|--------|------|
| quick | 快速检查用例，执行时间短 |
| smoke | 冒烟测试用例 |
| core | 核心功能用例 |
| main | 主要业务流程 |
| popup | 弹框相关测试 |
| ui | 界面元素测试 |

## Allure 报告生成

### 自动生成（推荐）
```bash
python run_suite.py --group "快速检查"
```

### 手动生成
```bash
# 先运行测试
python run_suite.py --group "快速检查"

# 生成报告
allure generate allure-results -o allure-report --clean

# 打开报告
allure open allure-report
```

## 多环境运行

在 `config/settings.yaml` 的 `execution.env` 中选择环境（默认 `dev`）：

```yaml
execution:
  env: "dev"
environments:
  dev:
    base_url: "https://www.znzmo.com/?from=personalCenter"
    headless: false
    default_timeout_ms: 30000
  test:
    base_url: "https://example.com"
    headless: true
    default_timeout_ms: 12000
```

## 统一配置管理

### 配置优先级
框架使用统一的配置管理模块 `config/settings.py`，支持以下配置优先级（从高到低）：

1. **命令行参数** - 最高优先级
2. **环境变量** - 中等优先级
3. **配置文件** - 最低优先级

### 配置文件
- `config/settings.yaml` - 主要环境配置
- `test_suite.yaml` - 测试分组和执行配置

### 命令行参数
```bash
# 环境配置
--env=dev                    # 测试环境（dev/test/prod）
--base-url=https://...       # 基础URL
--headless                   # 无头模式运行
--no-headless                # 非无头模式运行

# 执行配置
--workers=4                  # 并发进程数
--dist-mode=file             # 并发分发模式（file/class/function）
--max-reruns=2               # 最大重试次数
--reruns-delay=1             # 重试延迟（秒）
--no-reruns                  # 禁用重试

# Allure配置
--no-allure                  # 禁用Allure报告
--allure-results=dir         # Allure结果目录
--no-open-report             # 不自动打开Allure报告
```

### 环境变量
```bash
TEST_ENV=dev
TEST_BASE_URL=https://...
TEST_HEADLESS=true
TEST_WORKERS=4
TEST_MAX_RERUNS=2
TEST_RERUNS_DELAY=1
```

### Python中使用配置
```python
from config.settings import get_config

config = get_config()

# 访问环境配置
print(f"环境: {config.env.value}")
print(f"基础URL: {config.current_env.base_url}")
print(f"无头模式: {config.current_env.headless}")

# 访问执行配置
print(f"并发: {config.execution.parallel_workers}")
print(f"重试: {config.execution.retry_max_reruns}")

# 访问Allure配置
print(f"Allure: {config.allure.enabled}")
```

### 配置校验
框架启动时会自动校验以下必填配置：
- 基础URL(base_url)必须配置且以http开头
- 超时时间必须大于0
- 并发进程数必须大于0
- 重试次数和延迟不能小于0
- 浏览器类型必须支持(chromium/firefox/webkit)

## 并发执行优化

### pytest-xdist 配置
框架已优化 pytest-xdist 配置，避免共享资源竞争问题：

- **使用 loadfile 分发模式** - 按文件分配测试到不同 worker
- **每个测试文件在一个 worker 中执行** - 避免同一个类的测试分散
- **减少 worker 间的资源竞争** - 更好的本地资源隔离

### 并发配置
在 `test_suite.yaml` 中配置：
```yaml
execution:
  parallel:
    enabled: true
    workers: 2          # 建议2-4个worker（Playwright资源消耗大）
    dist_mode: file    # 按文件分发
```

### 并发执行示例
```bash
# 使用配置文件中的并发设置
python run_suite.py --group "核心功能"

# 强制启用并发并指定进程数
python run_suite.py --group "核心功能" --parallel --workers 4

# 禁用并发执行（单进程运行）
python run_suite.py --group "快速检查" --no-parallel

# 自定义并发分发模式
python run_suite.py --tags popup ui --dist-mode class
```

### 并发测试最佳实践
- 避免共享状态：使用 pytest fixtures 而非全局变量
- 文件操作使用临时目录
- 数据库操作使用独立连接或事务回滚
- 浏览器资源按进程隔离（已实现）

## 示例说明

### 测试数据
`tests/data/login_data.yaml`：
```yaml
cases:
  - case_name: "valid_login"
    username: "17768100279"
    password: "Qyff2011"
    expected_message: "登录成功"
```

### 测试用例
`tests/cases/test_login.py`：
```python
import pytest
from data_types.test_data_types import LoginCaseData
from pages.methods.login_page import LoginPage
from tests.steps.test_base import load_typed_cases_from_yaml, case_ids

LOGIN_CASES = load_typed_cases_from_yaml("tests/data/login_data.yaml", LoginCaseData)
LOGIN_CASE_IDS = case_ids(LOGIN_CASES)

class TestLogin:
    @pytest.mark.parametrize("case_data", LOGIN_CASES, ids=LOGIN_CASE_IDS)
    @pytest.mark.core
    @pytest.mark.main
    def test_login_success(self, case_data):
        login_page = LoginPage()
        login_page.goto_login_page()
        login_page.login_with(case_data.username, case_data.password)
        assert login_page.page.url != "https://www.znzmo.com/?from=personalCenter"
```

## Cookie 快捷登录

CookieManager 提供智能的 Cookie 管理和快捷登录功能：

### 核心功能
- **自动Cookie登录**：每次执行登录前检查本地是否存在有效Cookie
- **环境隔离存储**：按环境（dev/test/prod）独立存储Cookie文件
- **自动有效性验证**：检测Cookie过期时间（默认24小时）
- **失效自动回退**：Cookie无效时自动执行正常登录流程
- **登录成功保存**：自动保存新登录成功的Cookie

### 存储特点
- 文件位置：`core/` 目录下
- 文件命名：`cookies_{环境}_{账号标识}.json`
- 存储格式：JSON格式，包含Cookie内容和时间戳

## 架构特点
1. **POM 模式**：页面方法和元素分离，统一管理页面操作
2. **统一配置管理**：单例模式配置，支持命令行 > 环境变量 > 配置文件优先级
3. **环境隔离**：单文件配置多环境，支持开发、测试、生产环境切换
4. **测试数据管理**：YAML格式数据，支持标签过滤
5. **自动化断言**：断言失败自动截图和记录日志
6. **浏览器管理**：统一管理 Playwright 实例，按进程隔离支持并发
7. **分组执行**：YAML 配置灵活组合测试分组
8. **标签执行**：支持按标签灵活筛选和执行用例
9. **Allure 报告**：集成 Allure 测试报告，可视化展示结果
10. **并发执行优化**：pytest-xdist loadfile 分发模式，避免共享资源竞争
11. **异常类型定向重试**：支持对特定异常类型进行重试
12. **元素定位隔离**：从 YAML 文件读取定位器，而非硬编码在页面类中
13. **Cookie 快捷登录**：支持自动管理登录状态，显著提升执行效率
