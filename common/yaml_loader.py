from pathlib import Path
from typing import Any, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(relative_path: str) -> Any:
    file_path = PROJECT_ROOT / relative_path
    with file_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml_if_exists(relative_path: str) -> Optional[Any]:
    file_path = PROJECT_ROOT / relative_path
    if not file_path.exists():
        return None
    with file_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_dict(base: dict[str, Any], override: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not override:
        return dict(base)
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_dict(merged[key], value)
            continue
        merged[key] = value
    return merged
