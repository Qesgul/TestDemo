from typing import Any, Optional, TypeVar

from config.settings import ACTIVE_TAGS
from common.yaml_loader import load_yaml

T = TypeVar("T")


def active_tags() -> set[str]:
    return {tag.strip() for tag in ACTIVE_TAGS if tag.strip()}


def load_cases_from_yaml(relative_path: str, key: str = "cases") -> list[dict[str, Any]]:
    payload = load_yaml(relative_path) or {}
    return list(payload.get(key, []))


def filter_cases_by_tags(
    cases: list[dict[str, Any]],
    tags: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    runtime_tags = tags if tags is not None else active_tags()
    if not runtime_tags:
        return cases
    filtered: list[dict[str, Any]] = []
    for item in cases:
        case_tags = {str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()}
        if case_tags & runtime_tags:
            filtered.append(item)
    return filtered


def to_objects(cases: list[dict[str, Any]], data_type: type[T]) -> list[T]:
    return [data_type(**item) for item in cases]


def load_typed_cases_from_yaml(
    relative_path: str,
    data_type: type[T],
    key: str = "cases",
) -> list[T]:
    raw_cases = load_cases_from_yaml(relative_path, key=key)
    filtered_cases = filter_cases_by_tags(raw_cases)
    return to_objects(filtered_cases, data_type)


def case_ids(cases: list[Any], id_field: str = "case_name") -> list[str]:
    return [str(getattr(item, id_field)) for item in cases]


def get_case_by_name(cases: list[Any], case_name: str, id_field: str = "case_name") -> Any:
    for item in cases:
        if str(getattr(item, id_field)) == case_name:
            return item
    raise ValueError(f"Case data not found: {case_name}")
