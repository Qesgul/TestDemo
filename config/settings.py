"""
统一配置模块 - 收敛所有配置入口
支持配置优先级：命令行 > 环境变量 > 配置文件
"""
import os
import argparse
from pathlib import Path
from typing import Any, Dict, Optional, List
from enum import Enum
from common.yaml_loader import load_yaml, merge_dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Environment(Enum):
    """测试环境枚举"""
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class BrowserConfig:
    """浏览器配置类"""
    def __init__(self, config: Dict[str, Any]):
        self.name: str = config.get("name", "chromium")
        self.channel: str = config.get("channel", "")
        self.slow_mo_ms: int = config.get("slow_mo_ms", 0)
        self.launch_args: List[str] = config.get("launch_args", [])


class EnvironmentConfig:
    """环境配置类"""
    def __init__(self, config: Dict[str, Any]):
        self.base_url: str = config.get("base_url", "https://www.znzmo.com/")
        # Playwright 期望使用 `headless: bool`，这里同时兼容旧字段 `no_headless`
        # - headless: true/false 直接生效
        # - no_headless: true 等价于 headless: false
        if "headless" in config:
            self.headless = bool(config.get("headless", False))
        elif "no_headless" in config:
            self.headless = not bool(config.get("no_headless", False))
        else:
            self.headless = False
        self.default_timeout_ms: int = config.get("default_timeout_ms", 30000)
        self.browser: BrowserConfig = BrowserConfig(config.get("browser", {}))


class ExecutionConfig:
    """执行配置类"""
    def __init__(self, config: Dict[str, Any]):
        self.env: str = config.get("env", "dev")
        self.tags: List[str] = config.get("tags", [])
        self.default_mode: str = config.get("default_mode", "group")
        self.default_group: str = config.get("default_group", "核心功能")
        self.default_tags: List[str] = config.get("default_tags", [])

        # 并发执行配置
        parallel_config = config.get("parallel", {})
        self.parallel_enabled: bool = parallel_config.get("enabled", False)
        self.parallel_workers: int = parallel_config.get("workers", 2)
        self.parallel_dist_mode: str = parallel_config.get("dist_mode", "file")

        # 失败重试配置
        retry_config = config.get("retry", {})
        self.retry_enabled: bool = retry_config.get("enabled", True)
        self.retry_max_reruns: int = retry_config.get("max_reruns", 2)
        self.retry_delay: int = retry_config.get("reruns_delay", 1)
        self.retry_only_flaky: bool = retry_config.get("only_flaky", False)


class AllureConfig:
    """Allure报告配置类"""
    def __init__(self, config: Dict[str, Any]):
        self.enabled: bool = config.get("enabled", True)
        self.results_dir: str = config.get("results_dir", "allure-results")
        self.report_dir: str = config.get("report_dir", "allure-report")
        self.clean_results: bool = config.get("clean_results", True)
        self.open_report: bool = config.get("open_report", True)
        self.report_title: str = config.get("report_title", "知末网自动化测试报告")


class Config:
    """统一配置管理类"""

    # 配置文件路径
    CONFIG_PATHS = [
        "config/settings.yaml",
        "test_suite.yaml",
    ]

    # 环境变量前缀
    ENV_PREFIX = "TEST_"

    # 单例实例
    _instance: Optional["Config"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._config: Dict[str, Any] = {}
        self.env: Environment = Environment.DEV
        self.environments: Dict[str, EnvironmentConfig] = {}
        self.current_env: EnvironmentConfig = EnvironmentConfig({})
        self.cookie_dir: str = str(PROJECT_ROOT / "core")

        # 解析后的配置对象（会在后续应用覆盖逻辑后最终用于校验/快照）
        self._execution: Optional[ExecutionConfig] = None
        self._allure: Optional[AllureConfig] = None

        # 解析命令行参数（仅解析，不直接应用覆盖，避免依赖顺序）
        self._load_config_files()
        self.args = self._parse_args()

        # 先构建环境配置并解析最终环境与环境相关字段（base_url/headless）
        self._load_environment_config()
        self._load_path_config()

        # 再构建执行/Allure配置并应用命令行 + 环境变量覆盖
        self._execution = ExecutionConfig(self._config.get("execution", {}))
        self._allure = AllureConfig(self._config.get("allure", {}))

        self._apply_cli_overrides()
        self._parse_env_vars()

        self._validate_config()

    def _load_config_files(self):
        """加载配置文件"""
        self._config = {}
        for config_path in self.CONFIG_PATHS:
            file_path = PROJECT_ROOT / config_path
            if file_path.exists():
                try:
                    config = load_yaml(config_path)
                    if config:
                        self._config = merge_dict(self._config, config)
                except Exception as e:
                    raise RuntimeError(f"加载配置文件失败 {config_path}: {e}")

    def _load_environment_config(self):
        """构建环境配置并解析最终环境 + 环境相关字段覆盖（base_url/headless）"""
        environments_config = self._config.get("environments", {}) or {}
        self.environments = {
            env_name: EnvironmentConfig(env_config)
            for env_name, env_config in environments_config.items()
        }

        env_from_file = str(self._config.get("execution", {}).get("env", Environment.DEV.value)).lower()
        env_from_env = os.environ.get("TEST_ENV")
        env_from_cli = getattr(self.args, "env", None)

        resolved_env = str(env_from_cli if env_from_cli is not None else (env_from_env or env_from_file)).lower()
        self.env = Environment(resolved_env)

        if self.env.value not in self.environments:
            raise ValueError(
                f"配置的 execution.env='{self.env.value}' 不存在，请检查 settings.yaml 的 environments 节点"
            )

        self.current_env = self.environments[self.env.value]

        # base_url：命令行 > 环境变量 > 配置文件
        if self.args.base_url is not None:
            self.current_env.base_url = self.args.base_url
        elif "TEST_BASE_URL" in os.environ:
            self.current_env.base_url = os.environ["TEST_BASE_URL"]

        # headless：命令行 > 环境变量 > 配置文件（Playwright: headless: bool）
        headless_cli = None
        if getattr(self.args, "headless", None) is True and getattr(self.args, "no_headless", None) is True:
            raise ValueError("参数冲突：同时指定了 --headless 和 --no-headless")
        if getattr(self.args, "headless", None) is True:
            headless_cli = True
        elif getattr(self.args, "no_headless", None) is True:
            headless_cli = False

        if headless_cli is not None:
            self.current_env.headless = headless_cli
        elif "TEST_HEADLESS" in os.environ:
            # 允许 true/false/1/0/yes/no 等
            test_headless_raw = os.environ["TEST_HEADLESS"].strip().lower()
            self.current_env.headless = test_headless_raw in {"true", "1", "yes", "y", "on"}

    def _load_path_config(self) -> None:
        """加载路径类配置（例如 cookie 存储目录）"""
        path_config = self._config.get("paths", {}) or {}
        raw_cookie_dir = path_config.get("cookie_dir", "core")

        cookie_dir_path = Path(str(raw_cookie_dir))
        if not cookie_dir_path.is_absolute():
            cookie_dir_path = PROJECT_ROOT / cookie_dir_path

        if "TEST_COOKIE_DIR" in os.environ:
            env_cookie_dir = Path(os.environ["TEST_COOKIE_DIR"])
            if not env_cookie_dir.is_absolute():
                env_cookie_dir = PROJECT_ROOT / env_cookie_dir
            cookie_dir_path = env_cookie_dir

        self.cookie_dir = str(cookie_dir_path.resolve())

    def _parse_args(self):
        """解析命令行参数（不直接应用覆盖逻辑）"""
        parser = argparse.ArgumentParser(description="自动化测试配置")

        # 环境配置
        parser.add_argument(
            "--env",
            action="store",
            choices=["dev", "test", "prod"],
            help="测试环境（默认: dev）"
        )
        parser.add_argument(
            "--base-url",
            action="store",
            help="基础URL（默认: 配置文件中的值）"
        )
        parser.add_argument(
            "--headless",
            action="store_true",
            default=None,
            help="无头模式运行（默认: 配置文件中的值）"
        )
        parser.add_argument(
            "--no-headless",
            action="store_true",
            default=None,
            help="非无头模式运行"
        )

        # 执行配置
        parser.add_argument(
            "--tags",
            nargs="+",
            help="测试标签（默认: 配置文件中的值）"
        )
        parser.add_argument(
            "--workers",
            type=int,
            help="并发进程数（默认: 2）"
        )
        parser.add_argument(
            "--dist-mode",
            action="store",
            choices=["file", "class", "function"],
            help="并发分发模式（默认: file）"
        )
        parser.add_argument(
            "--max-reruns",
            type=int,
            help="最大重试次数（默认: 2）"
        )
        parser.add_argument(
            "--reruns-delay",
            type=int,
            help="重试延迟（秒）（默认: 1）"
        )
        parser.add_argument(
            "--no-reruns",
            action="store_true",
            default=None,
            help="禁用重试"
        )

        # Allure配置
        parser.add_argument(
            "--no-allure",
            action="store_true",
            default=None,
            help="禁用Allure报告"
        )
        parser.add_argument(
            "--allure-results",
            action="store",
            help="Allure结果目录（默认: allure-results）"
        )
        parser.add_argument(
            "--allure-report",
            action="store",
            help="Allure报告目录（默认: allure-report）"
        )
        parser.add_argument(
            "--no-open-report",
            action="store_true",
            default=None,
            help="不自动打开Allure报告"
        )

        args, _ = parser.parse_known_args()
        return args

    def _parse_env_vars(self):
        """解析环境变量（只处理命令行未指定的执行类字段覆盖）"""
        # 并发：命令行 > 环境变量 > 配置文件
        if "TEST_WORKERS" in os.environ and self.args.workers is None:
            self.execution.parallel_workers = int(os.environ["TEST_WORKERS"])

        # 重试次数：命令行 > 环境变量 > 配置文件
        if "TEST_MAX_RERUNS" in os.environ and self.args.max_reruns is None:
            self.execution.retry_max_reruns = int(os.environ["TEST_MAX_RERUNS"])

        # 重试延迟：命令行 > 环境变量 > 配置文件
        if "TEST_RERUNS_DELAY" in os.environ and self.args.reruns_delay is None:
            self.execution.retry_delay = int(os.environ["TEST_RERUNS_DELAY"])

    def _apply_cli_overrides(self) -> None:
        """应用命令行参数覆盖（执行类 & Allure）"""
        # 执行配置
        if self.args.tags is not None:
            self.execution.tags = self.args.tags
        if self.args.workers is not None:
            self.execution.parallel_workers = self.args.workers
        if self.args.dist_mode is not None:
            self.execution.parallel_dist_mode = self.args.dist_mode
        if self.args.max_reruns is not None:
            self.execution.retry_max_reruns = self.args.max_reruns
        if self.args.reruns_delay is not None:
            self.execution.retry_delay = self.args.reruns_delay
        if self.args.no_reruns is True:
            self.execution.retry_enabled = False

        # Allure
        if self.args.no_allure is True:
            self.allure.enabled = False
        if self.args.allure_results is not None:
            self.allure.results_dir = self.args.allure_results
        if self.args.allure_report is not None:
            self.allure.report_dir = self.args.allure_report
        if self.args.no_open_report is True:
            self.allure.open_report = False

    def _validate_config(self):
        """校验配置"""
        # 校验必填配置
        if not self.current_env.base_url:
            raise ValueError("配置错误: 基础URL(base_url)未配置")

        if not self.current_env.base_url.startswith("http"):
            raise ValueError(f"配置错误: 基础URL({self.current_env.base_url})格式无效")

        if self.current_env.default_timeout_ms <= 0:
            raise ValueError(f"配置错误: 超时时间({self.current_env.default_timeout_ms})必须大于0")

        if self.env.value not in self.environments:
            raise ValueError(
                f"配置的 execution.env='{self.env.value}' 不存在，请检查 settings.yaml 的 environments 节点"
            )

        # 校验并发配置
        if self.execution.parallel_workers < 1:
            raise ValueError(f"配置错误: 并发进程数({self.execution.parallel_workers})必须大于0")

        # 校验重试配置
        if self.execution.retry_max_reruns < 0:
            raise ValueError(f"配置错误: 重试次数({self.execution.retry_max_reruns})不能小于0")

        if self.execution.retry_delay < 0:
            raise ValueError(f"配置错误: 重试延迟({self.execution.retry_delay})不能小于0")

        # 校验浏览器配置
        if self.current_env.browser.name not in ["chromium", "firefox", "webkit"]:
            raise ValueError(f"配置错误: 浏览器类型({self.current_env.browser.name})不支持")

    @property
    def execution(self) -> ExecutionConfig:
        """获取执行配置"""
        if self._execution is None:
            self._execution = ExecutionConfig(self._config.get("execution", {}))
        return self._execution

    @property
    def allure(self) -> AllureConfig:
        """获取Allure配置"""
        if self._allure is None:
            self._allure = AllureConfig(self._config.get("allure", {}))
        return self._allure

# 创建单例实例
config = Config()


def get_config() -> Config:
    """获取配置实例的便捷方法"""
    return config


# 保持向后兼容性的全局变量：以“解析后配置快照”为准
BASE_URL = config.current_env.base_url
HEADLESS = config.current_env.headless
DEFAULT_TIMEOUT_MS = config.current_env.default_timeout_ms
ACTIVE_TAGS = [str(tag).strip() for tag in config.execution.tags if str(tag).strip()]

BROWSER_NAME = str(config.current_env.browser.name).lower()
BROWSER_CHANNEL = str(config.current_env.browser.channel).strip()
BROWSER_SLOW_MO_MS = int(config.current_env.browser.slow_mo_ms)
BROWSER_LAUNCH_ARGS = [str(arg) for arg in config.current_env.browser.launch_args]

if __name__ == "__main__":
    # 打印配置信息（用于调试）
    print("当前配置:")
    print(f"  环境: {config.env.value}")
    print(f"  基础URL: {config.current_env.base_url}")
    print(f"  无头模式: {config.current_env.headless}")
    print(f"  超时时间: {config.current_env.default_timeout_ms}ms")
    print(f"  浏览器: {config.current_env.browser.name}")
    print(f"  并发: {config.execution.parallel_enabled}, workers: {config.execution.parallel_workers}")
    print(f"  重试: {config.execution.retry_enabled}, reruns: {config.execution.retry_max_reruns}")
    print(f"  Allure: {config.allure.enabled}")
    print("-" * 60)

    # 打印所有环境配置
    print("所有环境配置:")
    for env_name, env_config in config.environments.items():
        print(f"  {env_name}: {env_config.base_url}")
