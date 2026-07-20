# -*- coding: utf-8 -*-
"""
AI 绘图会员档位取号 + 登录态复用封装（260618 需求）

作用
----
按「会员档位」从账号池取号，并复用 storage_state 启动登录态，
供 5 档会员 × 定价核对类用例统一取账号，避免每条用例重复登录。

档位 -> 账号池 tag 映射（tag 走 snake_case，新增前已 grep 现有标签复用风格）
------------------------------------------------------------------------
  ai_member_normal_new   普通会员-新用户（区分老会员的精准渲染-标准可用性）
  ai_member_normal_old   普通会员-老会员（精准渲染-标准仅老会员可用）
  ai_member_gold         黄金会员
  ai_member_platinum     铂金会员
  ai_member_diamond      钻石会员
  ai_member_black_gold   黑金会员

现状缺口（据实，勿臆造）
------------------------
  截至产出时，tests/data/account_pool.yaml 仅 3 个账号，且【没有】上述任何
  AI 会员档位 tag、也没有 ai.znzmo.cn 账号。因此 get_account 取不到时会
  明确报错并提示「请按 tag 补录账号到 account_pool.yaml」——绝不臆造账号/密码。

跨 TLD 约定（据实）
-------------------
  目标站点 https://ai.znzmo.cn 与 znzmo.com 是不同 TLD（.cn vs .com）。
  common/api/auth.py 的 CAS 登录是 .com 专用，对 .cn 完全无效。
  故登录态复用走 .cn 站自身的 UI 登录（ensure_storage_state 内部 znzmo_ui_login），
  不套用 .com 的 cookie / CAS session。

副作用
------
  只读 account_pool.yaml。get_storage_state 会触发一次 .cn 站 UI 登录并缓存
  storage_state（写 .auth/ 下登录态 JSON），属登录态缓存、非业务造数。
  不写库 / 不切量 / 不改账号池 / 不碰生产代码。

执行约定
--------
  默认 main 为 dry-run：只打印「档位 -> tag -> 是否在池中找到」清单，
  不启动浏览器、不触发登录。带 --login 才会对找到的档位实际预热 storage_state。

用法
----
  python utils/ai_member_account.py                 # dry-run，打印取号情况
  python utils/ai_member_account.py --tier gold     # 仅检查某档位
  python utils/ai_member_account.py --login --tier gold  # 实际预热该档位登录态
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# 目标站点（.cn，独立 TLD）
AI_SITE_URL = "https://ai.znzmo.cn"

# 账号池路径（authoring-time，只读）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACCOUNT_POOL_PATH = _PROJECT_ROOT / "tests" / "data" / "account_pool.yaml"

# 档位 -> 账号池 tag 映射
TIER_TAG_MAP = {
    "normal_new": "ai_member_normal_new",
    "normal_old": "ai_member_normal_old",
    "gold": "ai_member_gold",
    "platinum": "ai_member_platinum",
    "diamond": "ai_member_diamond",
    "black_gold": "ai_member_black_gold",
}

# 档位中文名（仅用于打印，便于人工核对）
TIER_CN = {
    "normal_new": "普通会员-新用户",
    "normal_old": "普通会员-老会员",
    "gold": "黄金会员",
    "platinum": "铂金会员",
    "diamond": "钻石会员",
    "black_gold": "黑金会员",
}


class AccountNotFoundError(LookupError):
    """档位对应 tag 在账号池中无匹配账号时抛出。"""


def _load_pool() -> list[dict]:
    """只读加载账号池 accounts 列表。"""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("缺少 PyYAML 依赖，请在项目 .venv 内安装") from exc

    if not ACCOUNT_POOL_PATH.exists():
        raise FileNotFoundError(f"账号池不存在：{ACCOUNT_POOL_PATH}")

    data = yaml.safe_load(ACCOUNT_POOL_PATH.read_text(encoding="utf-8")) or {}
    return data.get("accounts", []) or []


def _tag_for_tier(tier: str) -> str:
    if tier not in TIER_TAG_MAP:
        raise KeyError(
            f"未知档位 '{tier}'，可选：{', '.join(TIER_TAG_MAP)}"
        )
    return TIER_TAG_MAP[tier]


def get_account(tier: str) -> dict:
    """
    按档位从账号池取一条账号。

    Returns:
        {"username": ..., "password": ..., "tags": [...], ...}

    Raises:
        AccountNotFoundError: 池中无该 tag 的账号——附补录提示，不返回假账号。
    """
    tag = _tag_for_tier(tier)
    for acc in _load_pool():
        if tag in (acc.get("tags") or []):
            return acc
    raise AccountNotFoundError(
        f"账号池中找不到档位 '{tier}'（tag={tag}）对应的账号。\n"
        f"请按以下 tag 补录 AI 绘图会员账号到：{ACCOUNT_POOL_PATH}\n"
        f"  追加一条 entry，tags 包含 '{tag}'（{TIER_CN.get(tier, tier)}）。\n"
        f"（脚本只读账号池，绝不自动写入或臆造账号/密码。）"
    )


def get_storage_state(
    tier: str, *, headless: bool = True, max_age_hours: float = 12
) -> Optional[str]:
    """
    取该档位账号并复用 storage_state，返回 state JSON 路径。

    走 ai.znzmo.cn 自身 UI 登录（ensure_storage_state 内部），不套用 .com CAS。
    无凭据时 ensure_storage_state 返回 None（匿名降级）。

    Raises:
        AccountNotFoundError: 池中无该档位账号（先于登录抛出）。
    """
    acc = get_account(tier)
    # 延迟导入，dry-run 路径不依赖 playwright
    from common.selector_finder.login_session import ensure_storage_state

    return ensure_storage_state(
        AI_SITE_URL,
        acc.get("username"),
        acc.get("password"),
        headless=headless,
        max_age_hours=max_age_hours,
    )


def _check_one(tier: str) -> dict:
    """dry-run：检查单档位取号情况，不登录。"""
    tag = TIER_TAG_MAP[tier]
    result = {"tier": tier, "tier_cn": TIER_CN[tier], "tag": tag, "found": False, "username": None}
    try:
        acc = get_account(tier)
        result["found"] = True
        result["username"] = acc.get("username")
    except AccountNotFoundError:
        pass
    return result


def build_report(rows: list[dict]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  AI 会员档位取号自检（dry-run，未登录）")
    lines.append(f"  账号池：{ACCOUNT_POOL_PATH}")
    lines.append(f"  目标站点：{AI_SITE_URL}（.cn 独立 TLD，UI 登录，不套 .com CAS）")
    lines.append("=" * 60)
    missing = []
    for r in rows:
        flag = "OK  " if r["found"] else "缺号"
        uname = r["username"] or "-"
        lines.append(f"  [{flag}] {r['tier_cn']:<14} tag={r['tag']:<22} 账号={uname}")
        if not r["found"]:
            missing.append(r["tag"])
    lines.append("-" * 60)
    if missing:
        lines.append(f"待补录账号 tag（{len(missing)} 个）：")
        for t in missing:
            lines.append(f"  - {t}")
        lines.append("请按上述 tag 追加账号到账号池后重跑（脚本只读，不自动写入）。")
    else:
        lines.append("全部档位均已找到账号。")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AI 会员档位取号 + 登录态复用封装")
    parser.add_argument(
        "--tier", choices=list(TIER_TAG_MAP), default=None,
        help="只检查/预热指定档位（默认全部档位 dry-run）",
    )
    parser.add_argument(
        "--login", action="store_true",
        help="对找到的档位实际预热 storage_state（默认 dry-run 不登录）",
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="自检结果写到此 UTF-8 文件（默认打印到 stdout）",
    )
    args = parser.parse_args(argv)

    tiers = [args.tier] if args.tier else list(TIER_TAG_MAP)
    rows = [_check_one(t) for t in tiers]
    report = build_report(rows)

    # 实际登录预热（仅对找到的档位，且显式 --login）
    if args.login:
        extra = ["", "── storage_state 预热 ──"]
        for r in rows:
            if not r["found"]:
                extra.append(f"  [跳过] {r['tier_cn']}：账号池缺号，无法预热")
                continue
            try:
                path = get_storage_state(r["tier"])
                extra.append(f"  [预热] {r['tier_cn']}：state={path}")
            except Exception as exc:  # noqa: BLE001 — 预热失败如实记录不中断
                extra.append(f"  [失败] {r['tier_cn']}：{exc}")
        report = report + "\n".join(extra) + "\n"

    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
    else:
        try:
            sys.stdout.write(report)
        except UnicodeEncodeError:
            sys.stdout.write(
                "[提示] 终端编码无法输出中文，请用 --report <file> 写 UTF-8 文件后 Read\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
