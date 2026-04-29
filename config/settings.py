"""
Unified configuration loader.
Priority: CLI args > environment variables > config files.
"""

from __future__ import annotations

import argparse
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.yaml_loader import load_yaml, merge_dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Environment(Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class BrowserConfig:
    def __init__(self, config: Dict[str, Any]):
        self.name: str = str(config.get("name", "chromium"))
        self.channel: str = str(config.get("channel", ""))
        self.slow_mo_ms: int = int(config.get("slow_mo_ms", 0))
        self.launch_args: List[str] = [str(arg) for arg in config.get("launch_args", [])]


class EnvironmentConfig:
    def __init__(self, config: Dict[str, Any]):
        self.base_url: str = str(config.get("base_url", "https://www.znzmo.com/"))
        if "headless" in config:
            self.headless = bool(config.get("headless", False))
        elif "no_headless" in config:
            self.headless = not bool(config.get("no_headless", False))
        else:
            self.headless = False
        self.default_timeout_ms: int = int(config.get("default_timeout_ms", 30000))
        self.browser = BrowserConfig(config.get("browser", {}))


class ExecutionConfig:
    def __init__(self, config: Dict[str, Any]):
        self.env: str = str(config.get("env", "dev"))
        self.tags: List[str] = [str(tag).strip() for tag in config.get("tags", []) if str(tag).strip()]
        self.default_suite: str = str(config.get("default_suite", config.get("default_group", "core")))

        parallel_config = config.get("parallel", {})
        self.parallel_enabled: bool = bool(parallel_config.get("enabled", False))
        self.parallel_workers: int = int(parallel_config.get("workers", 2))
        self.parallel_dist_mode: str = str(parallel_config.get("dist_mode", "file"))

        retry_config = config.get("retry", {})
        self.retry_enabled: bool = bool(retry_config.get("enabled", True))
        self.retry_max_reruns: int = int(retry_config.get("max_reruns", 2))
        self.retry_delay: int = int(retry_config.get("reruns_delay", 1))
        self.retry_only_flaky: bool = bool(retry_config.get("only_flaky", False))


class AllureConfig:
    def __init__(self, config: Dict[str, Any]):
        self.enabled: bool = bool(config.get("enabled", True))
        self.results_dir: str = str(config.get("results_dir", "allure-results"))
        self.report_dir: str = str(config.get("report_dir", "allure-report"))
        self.clean_results: bool = bool(config.get("clean_results", True))
        self.open_report: bool = bool(config.get("open_report", True))
        self.report_title: str = str(config.get("report_title", "自动化测试报告"))


class Config:
    CONFIG_PATHS = [
        "config/settings.yaml",
        "test_suite.yaml",
    ]

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
        self._execution: Optional[ExecutionConfig] = None
        self._allure: Optional[AllureConfig] = None

        self._load_config_files()
        self.args = self._parse_args()
        self._load_environment_config()
        self._load_path_config()
        self._execution = ExecutionConfig(self._config.get("execution", {}))
        self._allure = AllureConfig(self._config.get("allure", {}))
        self._apply_cli_overrides()
        self._parse_env_vars()
        self._validate_config()

    def _load_config_files(self) -> None:
        self._config = {}
        for config_path in self.CONFIG_PATHS:
            file_path = PROJECT_ROOT / config_path
            if not file_path.exists():
                continue
            try:
                config = load_yaml(config_path)
                if config:
                    self._config = merge_dict(self._config, config)
            except Exception as exc:
                raise RuntimeError(f"Failed to load config file {config_path}: {exc}") from exc

    def _load_environment_config(self) -> None:
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
                f"Configured execution.env='{self.env.value}' does not exist in settings.yaml environments"
            )

        self.current_env = self.environments[self.env.value]

        if self.args.base_url is not None:
            self.current_env.base_url = self.args.base_url
        elif "TEST_BASE_URL" in os.environ:
            self.current_env.base_url = os.environ["TEST_BASE_URL"]

        headless_cli = None
        if self.args.headless and (self.args.no_headless or self.args.headed):
            raise ValueError("Conflicting flags: --headless and --no-headless/--headed")
        if self.args.headless:
            headless_cli = True
        elif self.args.no_headless or self.args.headed:
            headless_cli = False

        if headless_cli is not None:
            self.current_env.headless = headless_cli
        elif "TEST_HEADLESS" in os.environ:
            self.current_env.headless = os.environ["TEST_HEADLESS"].strip().lower() in {
                "true",
                "1",
                "yes",
                "y",
                "on",
            }

    def _load_path_config(self) -> None:
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

    def _parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Automation test config parser")
        parser.add_argument("--env", choices=["dev", "test", "prod"])
        parser.add_argument("--base-url")
        parser.add_argument("--headless", action="store_true", default=None)
        parser.add_argument("--no-headless", action="store_true", default=None)
        parser.add_argument("--headed", action="store_true", default=None)
        parser.add_argument("--tags", nargs="+")
        parser.add_argument("--workers", type=int)
        parser.add_argument("--dist-mode", choices=["file", "class", "function"])
        parser.add_argument("--max-reruns", type=int)
        parser.add_argument("--reruns-delay", type=int)
        parser.add_argument("--no-reruns", action="store_true", default=None)
        parser.add_argument("--no-allure", action="store_true", default=None)
        parser.add_argument("--allure-results")
        parser.add_argument("--allure-report")
        parser.add_argument("--no-open-report", action="store_true", default=None)
        args, _ = parser.parse_known_args()
        return args

    def _parse_env_vars(self) -> None:
        if "TEST_WORKERS" in os.environ and self.args.workers is None:
            self.execution.parallel_workers = int(os.environ["TEST_WORKERS"])
        if "TEST_TAGS" in os.environ and self.args.tags is None:
            self.execution.tags = [
                tag.strip()
                for tag in os.environ["TEST_TAGS"].split(",")
                if tag.strip()
            ]
        if "TEST_MAX_RERUNS" in os.environ and self.args.max_reruns is None:
            self.execution.retry_max_reruns = int(os.environ["TEST_MAX_RERUNS"])
        if "TEST_RERUNS_DELAY" in os.environ and self.args.reruns_delay is None:
            self.execution.retry_delay = int(os.environ["TEST_RERUNS_DELAY"])

    def _apply_cli_overrides(self) -> None:
        if self.args.tags is not None:
            self.execution.tags = [str(tag).strip() for tag in self.args.tags if str(tag).strip()]
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

        if self.args.no_allure is True:
            self.allure.enabled = False
        if self.args.allure_results is not None:
            self.allure.results_dir = self.args.allure_results
        if self.args.allure_report is not None:
            self.allure.report_dir = self.args.allure_report
        if self.args.no_open_report is True:
            self.allure.open_report = False

    def _validate_config(self) -> None:
        if not self.current_env.base_url:
            raise ValueError("Missing base_url")
        if not self.current_env.base_url.startswith("http"):
            raise ValueError(f"Invalid base_url: {self.current_env.base_url}")
        if self.current_env.default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms must be greater than 0")
        if self.execution.parallel_workers < 1:
            raise ValueError("parallel workers must be greater than 0")
        if self.execution.retry_max_reruns < 0:
            raise ValueError("retry max reruns cannot be negative")
        if self.execution.retry_delay < 0:
            raise ValueError("retry delay cannot be negative")
        if self.current_env.browser.name not in ["chromium", "firefox", "webkit"]:
            raise ValueError(f"Unsupported browser type: {self.current_env.browser.name}")

    @property
    def execution(self) -> ExecutionConfig:
        if self._execution is None:
            self._execution = ExecutionConfig(self._config.get("execution", {}))
        return self._execution

    @property
    def allure(self) -> AllureConfig:
        if self._allure is None:
            self._allure = AllureConfig(self._config.get("allure", {}))
        return self._allure


config = Config()


def get_config() -> Config:
    return config


BASE_URL = config.current_env.base_url
HEADLESS = config.current_env.headless
DEFAULT_TIMEOUT_MS = config.current_env.default_timeout_ms
ACTIVE_TAGS = [str(tag).strip() for tag in config.execution.tags if str(tag).strip()]

BROWSER_NAME = str(config.current_env.browser.name).lower()
BROWSER_CHANNEL = str(config.current_env.browser.channel).strip()
BROWSER_SLOW_MO_MS = int(config.current_env.browser.slow_mo_ms)
BROWSER_LAUNCH_ARGS = [str(arg) for arg in config.current_env.browser.launch_args]
