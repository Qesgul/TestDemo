from common.yaml_loader import load_yaml

_settings = load_yaml("config/settings.yaml")
_execution = _settings.get("execution", {})
_all_envs = _settings.get("environments", {})
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
