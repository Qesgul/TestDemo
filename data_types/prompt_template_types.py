"""智能生图提示词模板扩充 - 数据类型定义。"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TemplateCard:
    """模板卡片数据。"""
    name: str
    is_personal: bool = False
    is_favorited: bool = False
    has_cover: bool = True


@dataclass
class SearchResult:
    """搜索结果。"""
    keyword: str
    total_count: int = 0
    template_names: List[str] = field(default_factory=list)
    is_empty: bool = False


@dataclass
class SearchScoring:
    """搜索排序评分规则。"""
    name_exact_match: int = 100
    name_contains_full_query: int = 80
    name_partial_keyword: int = 20  # 每命中一个词
    name_partial_max: int = 60
    content_contains_full_query: int = 30
    content_partial_keyword: int = 5  # 每命中一个词（去重）
    content_partial_max: int = 20


@dataclass
class NewTemplateData:
    """新建模板数据。"""
    name: str = ""
    content: str = ""
    cover_path: Optional[str] = None


@dataclass
class ValidationResult:
    """校验结果。"""
    is_valid: bool
    error_message: str = ""
    toast_text: str = ""
