"""按需求分组的 GIO 埋点期望：数据类 + 从 {feature}_data.yaml 的 tracking 段加载。

一个功能数据文件 = 一个需求批次。tracking 段结构见 recharge_flow_data.yaml。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from common.yaml_loader import load_yaml


@dataclass
class GioExpectation:
    identifier: str
    name: str = ""
    trigger: str = ""
    expect_vars: dict = field(default_factory=dict)
    status: str = "active"          # active | pending
    groups: list = field(default_factory=list)

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"


def parse_tracking_section(section: Optional[dict]) -> list[GioExpectation]:
    if not section:
        return []
    events = section.get("events") or []
    result: list[GioExpectation] = []
    for e in events:
        if not isinstance(e, dict) or not e.get("identifier"):
            continue
        result.append(GioExpectation(
            identifier=e["identifier"],
            name=e.get("name", ""),
            trigger=e.get("trigger", ""),
            expect_vars=e.get("expect_vars") or {},
            status=e.get("status", "active"),
            groups=e.get("groups") or [],
        ))
    return result


def load_gio_expectations(feature_yaml: str) -> list[GioExpectation]:
    """读取功能数据 YAML 的 tracking 段，返回埋点期望列表。"""
    data = load_yaml(feature_yaml) or {}
    return parse_tracking_section(data.get("tracking"))
