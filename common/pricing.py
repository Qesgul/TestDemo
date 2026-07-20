"""
统一价格查询模块 — 从 pricing_baseline.yaml 读取预期价格。

所有定价测试用例和 API 脚本通过本模块获取预期值，确保单一数据源。

用法：
    from common.pricing import get_expected_price, get_api_params, get_member_account

    # 查询价格
    price = get_expected_price("精准渲染", "标准模式", "新钻石会员")  # → 6
    price = get_expected_price("Agent模式", "GPT Image 2", "新钻石会员", "peak")  # → 12

    # 获取 API 参数
    params = get_api_params("精准渲染", "思考模式")  # → {serviceType: "16", ...}

    # 获取账号
    account = get_member_account("新钻石会员")  # → {username: "17768100279", ...}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from common.yaml_loader import load_yaml

_logger = logging.getLogger(__name__)

_BASELINE_PATH = "tests/data/pricing_baseline.yaml"
_cache: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    """加载并缓存价格基准数据。"""
    global _cache
    if _cache is None:
        _cache = load_yaml(_BASELINE_PATH)
        if not _cache:
            raise FileNotFoundError(
                f"价格基准文件未找到或为空: {_BASELINE_PATH}"
            )
    return _cache


def reload() -> None:
    """强制重新加载（用于测试或动态刷新）。"""
    global _cache
    _cache = None


# ── 价格查询 ──────────────────────────────────────────────────────────────────


def get_expected_price(
    product: str,
    combination: str,
    member: str,
    period: str = "normal",
) -> Optional[int]:
    """
    查询预期价格。

    :param product: 产品名（如 "Agent模式", "精准渲染", "创作渲染", "效果图美化"）
    :param combination: 组合名（如 "GPT Image 2", "标准模式", "思考模式", "Nano Banana Pro"）
    :param member: 会员等级（如 "新钻石会员", "普通会员"）
    :param period: 时段（"peak"/"normal"/"off_peak"，默认 "normal"）
    :return: 预期价格（知点），未配置则返回 None
    """
    data = _load()
    try:
        return data["pricing"][product][combination]["prices"][member][period]
    except (KeyError, TypeError):
        _logger.debug(
            "价格未配置: %s/%s/%s/%s", product, combination, member, period
        )
        return None


def get_api_params(product: str, combination: str) -> Optional[Dict[str, Any]]:
    """
    获取 API 请求参数。

    :param product: 产品名
    :param combination: 组合名
    :return: API 参数 dict，未配置则返回 None
    """
    data = _load()
    try:
        return dict(data["pricing"][product][combination]["api_params"])
    except (KeyError, TypeError):
        _logger.debug("API 参数未配置: %s/%s", product, combination)
        return None


# ── 账号查询 ──────────────────────────────────────────────────────────────────


def get_member_account(member: str) -> Optional[Dict[str, str]]:
    """
    获取会员账号信息。

    :param member: 会员等级名
    :return: {"username": "...", "password": "..."}，未配置则返回 None
    """
    data = _load()
    account = data.get("members", {}).get(member)
    if account and account.get("username") == "TODO":
        _logger.warning("账号待补充: %s", member)
        return None
    return account


def list_members() -> List[str]:
    """列出所有已配置的会员等级。"""
    data = _load()
    return list(data.get("members", {}).keys())


def list_combinations(product: Optional[str] = None) -> List[Dict[str, str]]:
    """
    列出所有已配置的价格组合。

    :param product: 指定产品名则只返回该产品的组合，None 则返回全部
    :return: [{"product": "...", "combination": "..."}]
    """
    data = _load()
    result = []
    pricing = data.get("pricing", {})
    products = [product] if product else list(pricing.keys())
    for p in products:
        for combo in pricing.get(p, {}):
            result.append({"product": p, "combination": combo})
    return result


def list_all_prices(
    product: Optional[str] = None,
    member: Optional[str] = None,
    period: str = "normal",
) -> List[Dict[str, Any]]:
    """
    列出所有价格条目（用于汇总展示）。

    :return: [{"product": ..., "combination": ..., "member": ..., "period": ..., "price": ...}]
    """
    data = _load()
    result = []
    pricing = data.get("pricing", {})
    products = [product] if product else list(pricing.keys())
    members = [member] if member else list(data.get("members", {}).keys())

    for p in products:
        for combo_name, combo in pricing.get(p, {}).items():
            prices = combo.get("prices", {})
            for m in members:
                price_data = prices.get(m, {})
                price = price_data.get(period)
                result.append({
                    "product": p,
                    "combination": combo_name,
                    "member": m,
                    "period": period,
                    "price": price,
                })
    return result
