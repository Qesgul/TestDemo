"""
selector_finder 数据模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedStep:
    """测试用例中的单个操作步骤。"""

    step_index: int
    description: str  # 原始步骤描述
    action: str  # click | fill | select | hover | check | assert
    element_desc: str  # 元素的自然语言描述
    value: Optional[str] = None  # fill 等操作的值


@dataclass
class LocatorSpec:
    """单个 Playwright 定位策略，可直接映射到 BasePage.get_locator() 的 YAML 格式。"""

    strategy: str  # role | label | placeholder | text | test_id | css

    # role
    role: Optional[str] = None
    name: Optional[str] = None
    exact: bool = False

    # label
    label: Optional[str] = None

    # placeholder
    placeholder: Optional[str] = None

    # text
    text: Optional[str] = None

    # test_id
    test_id: Optional[str] = None

    # css fallback
    selector: Optional[str] = None

    # 可选：先定位父容器，再在其内查找（解决多命中歧义）
    scope: Optional[str] = None

    def to_yaml_dict(self) -> dict:
        """转换为 BasePage.get_locator() 兼容的 YAML 字典。"""
        d: dict = {"type": self.strategy}
        if self.strategy == "role":
            d["role"] = self.role
            if self.name:
                d["name"] = self.name
            d["exact"] = self.exact
        elif self.strategy == "label":
            d["label"] = self.label
            d["exact"] = self.exact
        elif self.strategy == "placeholder":
            d["placeholder"] = self.placeholder
        elif self.strategy == "text":
            d["text"] = self.text
            d["exact"] = self.exact
        elif self.strategy == "test_id":
            d["test_id"] = self.test_id
        elif self.strategy == "css":
            d["selector"] = self.selector
        if self.scope:
            d["scope"] = self.scope
        return d


@dataclass
class ResolvedElement:
    """已解析（或等待人工补全）的元素。"""

    element_desc: str
    step_index: int
    action: str
    value: Optional[str] = None

    locator: Optional[LocatorSpec] = None  # 主定位策略
    alternatives: list[LocatorSpec] = field(default_factory=list)  # 备选策略

    verified: bool = False  # count() == 1 已验证
    # source 取值：human | yaml_reuse
    source: str = "human"
    attempts: int = 0


@dataclass
class SelectorReport:
    """完整的运行报告，供写入 YAML 使用。"""

    test_case_file: str
    target_url: str
    resolved: list[ResolvedElement] = field(default_factory=list)
    missing: list[ExtractedStep] = field(default_factory=list)  # 未人工点选的步骤

    @property
    def total(self) -> int:
        return len(self.resolved) + len(self.missing)

    @property
    def ai_count(self) -> int:
        return sum(1 for r in self.resolved if r.source in ("ai_first", "ai_self_heal"))

    @property
    def yaml_reuse_count(self) -> int:
        return sum(1 for r in self.resolved if r.source == "yaml_reuse")

    @property
    def human_count(self) -> int:
        return sum(1 for r in self.resolved if r.source == "human")
