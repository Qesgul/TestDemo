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
├─config/                   # 配置
│  ├─settings.yaml          # 单文件多环境配置yaml
│  └─settings.py            # 配置解析器，导出环境变量
├─core/                     # 框架核心基类
│  ├─browser_manager.py     # Playwright 浏览器生命周期管理
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

## 架构特点
1. **POM 模式**：页面方法和元素分离，统一管理页面操作
2. **环境隔离**：单文件配置多环境，支持开发、测试、生产环境切换
3. **测试数据管理**：YAML格式数据，支持标签过滤
4. **自动化断言**：断言失败自动截图和记录日志
5. **浏览器管理**：统一管理 Playwright 实例，避免重复创建
6. **分组执行**：YAML 配置灵活组合测试分组
7. **标签执行**：支持按标签灵活筛选和执行用例
8. **Allure 报告**：集成 Allure 测试报告，可视化展示结果
9. **并发执行**：支持多进程并行测试，提升执行效率
