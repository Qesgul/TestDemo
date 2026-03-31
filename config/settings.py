"""
统一配置模块 - 收敛所有配置入口
支持配置优先级：命令行 > 环境变量 > 配置文件
"""
import os
import yaml
import argparse
from pathlib import Path
from typing import Any, Dict, Optional, List, Union
from enum import Enum
from common.yaml_loader import load_yaml


class Environment(Enum):
    """测试环境枚举"""
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class BrowserType(Enum):
    """浏览器类型枚举"""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


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
        self.headless: bool = config.get("headless", False)
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

        # 加载配置文件
        self._load_config_files()

        # 解析命令行参数
        self._parse_args()

        # 解析环境变量
        self._parse_env_vars()

        # 校验配置
        self._validate_config()

    def _load_config_files(self):
        """加载配置文件"""
        self._config: Dict[str, Any] = {}

        for config_path in self.CONFIG_PATHS:
            if os.path.exists(config_path):
                try:
                    config = load_yaml(config_path)
                    if config:
                        self._merge_dict(self._config, config)
                except Exception as e:
                    raise RuntimeError(f"加载配置文件失败 {config_path}: {e}")

        # 加载环境特定配置
        self._load_environment_config()

    def _merge_dict(self, dest: Dict[str, Any], src: Dict[str, Any]) -> None:
        """递归合并字典"""
        for key, value in src.items():
            if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
                self._merge_dict(dest[key], value)
            else:
                dest[key] = value

    def _load_environment_config(self):
        """加载环境特定配置"""
        self.env: Environment = Environment(self._get_str_config("execution.env", "dev"))
        self.environments: Dict[str, EnvironmentConfig] = {}

        environments_config = self._config.get("environments", {})
        for env_name, env_config in environments_config.items():
            self.environments[env_name] = EnvironmentConfig(env_config)

        # 设置当前环境配置
        self.current_env: EnvironmentConfig = self.environments.get(self.env.value, EnvironmentConfig({}))

    def _parse_args(self):
        """解析命令行参数"""
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
            help="无头模式运行（默认: 配置文件中的值）"
        )
        parser.add_argument(
            "--no-headless",
            action="store_true",
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
            help="禁用重试"
        )

        # Allure配置
        parser.add_argument(
            "--no-allure",
            action="store_true",
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
            help="不自动打开Allure报告"
        )

        self.args, _ = parser.parse_known_args()

        # 应用命令行参数覆盖
        if self.args.env:
            self.env = Environment(self.args.env)
            if self.args.env in self.environments:
                self.current_env = self.environments[self.args.env]

        if self.args.base_url:
            self.current_env.base_url = self.args.base_url

        if self.args.headless:
            self.current_env.headless = True
        if self.args.no_headless:
            self.current_env.headless = False

        if self.args.tags:
            self.execution.tags = self.args.tags

        if self.args.workers is not None:
            self.execution.parallel_workers = self.args.workers

        if self.args.dist_mode:
            self.execution.parallel_dist_mode = self.args.dist_mode

        if self.args.max_reruns is not None:
            self.execution.retry_max_reruns = self.args.max_reruns

        if self.args.reruns_delay is not None:
            self.execution.retry_delay = self.args.reruns_delay

        if self.args.no_reruns:
            self.execution.retry_enabled = False

        if self.args.no_allure:
            self.allure.enabled = False

        if self.args.allure_results:
            self.allure.results_dir = self.args.allure_results

        if self.args.allure_report:
            self.allure.report_dir = self.args.allure_report

        if self.args.no_open_report:
            self.allure.open_report = False

    def _parse_env_vars(self):
        """解析环境变量"""
        # 解析环境变量配置，优先级：命令行 > 环境变量 > 配置文件
        if "TEST_ENV" in os.environ:
            if not hasattr(self, "args") or self.args.env is None:
                self.env = Environment(os.environ["TEST_ENV"])
                if self.env.value in self.environments:
                    self.current_env = self.environments[self.env.value]

        if "TEST_BASE_URL" in os.environ:
            if not hasattr(self, "args") or self.args.base_url is None:
                self.current_env.base_url = os.environ["TEST_BASE_URL"]

        if "TEST_HEADLESS" in os.environ:
            if not hasattr(self, "args") or self.args.headless is None and self.args.no_headless is None:
                self.current_env.headless = os.environ["TEST_HEADLESS"].lower() in ["true", "1"]

        if "TEST_WORKERS" in os.environ:
            if not hasattr(self, "args") or self.args.workers is None:
                self.execution.parallel_workers = int(os.environ["TEST_WORKERS"])

        if "TEST_MAX_RERUNS" in os.environ:
            if not hasattr(self, "args") or self.args.max_reruns is None:
                self.execution.retry_max_reruns = int(os.environ["TEST_MAX_RERUNS"])

        if "TEST_RERUNS_DELAY" in os.environ:
            if not hasattr(self, "args") or self.args.reruns_delay is None:
                self.execution.retry_delay = int(os.environ["TEST_RERUNS_DELAY"])

    def _validate_config(self):
        """校验配置"""
        # 校验必填配置
        if not self.current_env.base_url:
            raise ValueError("配置错误: 基础URL(base_url)未配置")

        if not self.current_env.base_url.startswith("http"):
            raise ValueError(f"配置错误: 基础URL({self.current_env.base_url})格式无效")

        if self.current_env.default_timeout_ms <= 0:
            raise ValueError(f"配置错误: 超时时间({self.current_env.default_timeout_ms})必须大于0")

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

    def _get_str_config(self, key: str, default: str = "") -> str:
        """获取字符串配置值"""
        parts = key.split(".")
        config = self._config
        for part in parts:
            if part in config:
                config = config[part]
            else:
                return default
        return str(config) if config is not None else default

    def _get_int_config(self, key: str, default: int = 0) -> int:
        """获取整数配置值"""
        parts = key.split(".")
        config = self._config
        for part in parts:
            if part in config:
                config = config[part]
            else:
                return default
        try:
            return int(config)
        except:
            return default

    def _get_bool_config(self, key: str, default: bool = False) -> bool:
        """获取布尔配置值"""
        parts = key.split(".")
        config = self._config
        for part in parts:
            if part in config:
                config = config[part]
            else:
                return default
        if isinstance(config, bool):
            return config
        if isinstance(config, str):
            return config.lower() in ["true", "1", "yes"]
        return bool(config)

    @property
    def execution(self) -> ExecutionConfig:
        """获取执行配置"""
        if not hasattr(self, "_execution"):
            self._execution = ExecutionConfig(self._config.get("execution", {}))
        return self._execution

    @property
    def allure(self) -> AllureConfig:
        """获取Allure配置"""
        if not hasattr(self, "_allure"):
            self._allure = AllureConfig(self._config.get("allure", {}))
        return self._allure


# 创建单例实例
config = Config()


def get_config() -> Config:
    """获取配置实例的便捷方法"""
    return config


# 保持向后兼容性的全局变量
_settings = config._config
_execution = config._config.get("execution", {})
_all_envs = config._config.get("environments", {})
_target_env = str(_execution.get("env", "dev")).lower()

if _target_env not in _all_envs:
    raise ValueError(f"配置的 execution.env='{_target_env}' 不存在，请检查 settings.yaml 的 environments 节点")

_active_env_settings = _all_envs[_target_env]
_browser_settings = _active_env_settings.get("browser", {})

BASE_URL = _active_env_settings["base_url"]
HEADLESS = _active_env_settings["headless"]
DEFAULT_TIMEOUT_MS = _active_env_settings["default_timeout_ms"]
ACTIVE_TAGS = [str(tag).strip() for tag in _execution.get("tags", []) if str(tag).strip()]
BROWSER_NAME = str(_browser_settings.get("name", "chromium")).lower()
BROWSER_CHANNEL = str(_browser_settings.get("channel", "")).strip()
BROWSER_SLOW_MO_MS = int(_browser_settings.get("slow_mo_ms", 0))
BROWSER_LAUNCH_ARGS = [str(arg) for arg in _browser_settings.get("launch_args", [])]

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
