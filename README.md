# Python + pytest + Playwright 自动化测试框架

## 技术栈

- Python
- pytest
- Playwright sync API
- PyYAML
- allure-pytest
- pytest-xdist

## 目录

```text
common/            公共能力
config/            统一配置
data_types/        测试数据类型
pages/             Page Object
tests/             测试用例与数据
run_suite.py       批量执行入口
test_suite.yaml    suite 定义
```

## 批量执行

项目现在采用 **suite-first** 的单入口模型。

日常只需要记住 3 个命令：

```bash
python run_suite.py list
python run_suite.py show core
python run_suite.py run core
```

### 1. 查看可用 suite

```bash
python run_suite.py list
```

### 2. 查看某个 suite 详情

```bash
python run_suite.py show core
```

### 3. 运行某个 suite

```bash
python run_suite.py run smoke
python run_suite.py run core
python run_suite.py run popup
```

### 4. 在 suite 内追加高级过滤

```bash
python run_suite.py run core --tags popup
```

### 5. 覆盖执行策略

```bash
python run_suite.py run core --workers 4
python run_suite.py run core --serial
python run_suite.py run core --reruns 3
python run_suite.py run core --no-reruns
```

### 6. 覆盖环境和报告

```bash
python run_suite.py run core --env test --headless
python run_suite.py run core --base-url https://example.com
python run_suite.py run core --no-allure
python run_suite.py run core --no-open-report
```

## suite 配置

`test_suite.yaml` 只负责定义“跑哪些用例”：

```yaml
default_suite: core

suites:
  - id: smoke
    name: 快速检查
    description: 最短路径回归
    cases:
      - tests/cases/test_check_popup.py::TestPopupDefaultDisplay::test_homepage_popup_default_display

  - id: core
    name: 核心功能
    description: 主业务回归
    cases:
      - tests/cases/test_homepage.py::TestHomePage::test_homepage_elements_displayed
      - tests/cases/test_login.py::TestLogin::test_login_success
```

说明：

- `id` 是命令行使用的 suite 标识
- `name` 是面向人的名称
- `description` 是说明
- `cases` 是 pytest 节点或文件路径
- `tags` 只作元数据和高级过滤参考，不再是主入口

## 执行默认项

`config/settings.yaml` 只放全局默认执行策略，例如：

```yaml
execution:
  env: "dev"
  default_suite: "core"
  parallel:
    enabled: true
    workers: 2
  retry:
    enabled: true
    max_reruns: 2
```

## 兼容说明

旧命令仍有一段兼容期，但会打印迁移提示：

```bash
python run_suite.py --group "核心功能"
python run_suite.py --list-groups
```

建议尽快改成：

```bash
python run_suite.py run core
python run_suite.py list
```

## 直接使用 pytest

高级场景仍可直接使用 pytest：

```bash
pytest
pytest tests/cases/test_login.py -q
pytest -m "core or main"
```

但 README 的主路径不再把它当作日常批量执行入口。
