# -*- coding: utf-8 -*-
r"""
AI 绘图账号知点余额造数 / 复位（260618 需求）—— 骨架，默认 dry-run

============================================================================
副作用登记（细则 E，执行前务必读）
============================================================================
  副作用类型 ：写 AI 绘图账号的知点余额（造数）——属写库/写状态级副作用。
  还原方式  ：reset_balance(account) 恢复账号默认余额；每次造数用后必复位。
  执行前置  ：
      1) 须用户明确确认后才可真实执行（规则 1：先打印造数计划，确认后落库）；
      2) 须提供 .cn 知点造数接口 / SQL（见下「接口缺口」）；
      3) 默认 --dry-run，不带真实写操作，main 不产生任何副作用。
  登记去向  ：套件级副作用登记表 / CONVERSION-REPORT 的「副作用与还原」清单。
============================================================================

作用
----
为下列用例造数：
  - 余额边界：余额 < 单价（扣费失败）、余额 == 单价（恰好可扣）、余额 = 单价-1
  - 免费格 0 扣：免费(0 知点)功能执行后余额不变
  - 连续扣减累计：多次扣费后余额累计正确

接口缺口（据实，勿臆造）
------------------------
  目标站 ai.znzmo.cn 是 .cn 独立 TLD；common/api 下的 CAS 鉴权仅 .com 有效，
  对 .cn 的知点造数接口 / SQL 目前【未知、未确认】。因此本脚本只给可运行骨架：
  真实造数实现处统一标 `# TODO(.cn 接口待研发确认)`，骨架默认 dry-run 不写库。
  研发确认接口后，仅需在 _apply_set_balance / _apply_reset_balance 内补实现。

执行约定
--------
  默认 main = dry-run：只打印「将要执行的造数计划」，不连库、不发请求。
  显式 --apply 才进入真实写路径——但当前真实写路径未实现（接口缺口），
  会主动抛错提示「请先补 .cn 造数接口并经用户确认」，绝不静默假装成功。

用法
----
  python utils/ai_zhidian_balance.py --account 13xxxxxxxxx --balance 5     # dry-run
  python utils/ai_zhidian_balance.py --account 13xxxxxxxxx --reset          # dry-run 复位计划
  python utils/ai_zhidian_balance.py --account 13xxxxxxxxx --balance 5 --apply  # 需接口+确认
"""

from __future__ import annotations

import argparse
import sys

# 默认余额（复位目标值）——占位常量，研发确认 .cn 默认态后修正。
# TODO(.cn 接口待研发确认): 默认余额到底是 0 还是按档位月度赠点，需研发给准。
DEFAULT_BALANCE = 0

AI_SITE = "ai.znzmo.cn"


class CaozhuInterfaceMissing(NotImplementedError):
    """.cn 知点造数接口未确认时，真实写路径抛此错（不静默成功）。"""


# ── 真实写实现（接口缺口，全部留 TODO） ────────────────────────────────────────
def _apply_set_balance(account: str, n: int) -> None:
    """
    真实将 account 的知点余额置为 n。

    TODO(.cn 接口待研发确认):
      研发确认后在此实现，二选一：
        a) HTTP：对 ai.znzmo.cn 造数接口 POST（需 .cn 自身鉴权 token，
           不可复用 common/api/auth.py 的 .com CAS）；
        b) SQL：直连测试库 UPDATE 知点余额表（需库连接信息 + 余额表/字段名）。
    """
    raise CaozhuInterfaceMissing(
        f"[{AI_SITE}] set_balance 真实写未实现：缺 .cn 知点造数接口/SQL。\n"
        f"请研发确认接口后补 _apply_set_balance，并经用户确认再 --apply。"
    )


def _apply_reset_balance(account: str) -> None:
    """
    真实将 account 的知点余额复位为 DEFAULT_BALANCE。

    TODO(.cn 接口待研发确认): 同 _apply_set_balance，实现复位写操作。
    """
    raise CaozhuInterfaceMissing(
        f"[{AI_SITE}] reset_balance 真实写未实现：缺 .cn 知点造数接口/SQL。\n"
        f"请研发确认接口后补 _apply_reset_balance，并经用户确认再 --apply。"
    )


# ── 对外接口：dry-run 默认；apply 才走真实写 ────────────────────────────────────
def set_balance(account: str, n: int, *, apply: bool = False) -> dict:
    """
    造数：将 account 知点余额置为 n。

    Args:
        apply: False=dry-run（仅返回计划，不写库）；True=真实写（需接口+用户确认）。
    """
    plan = {
        "op": "set_balance",
        "site": AI_SITE,
        "account": account,
        "target_balance": n,
        "applied": False,
    }
    if apply:
        _apply_set_balance(account, n)  # 接口缺口下会抛 CaozhuInterfaceMissing
        plan["applied"] = True
    return plan


def reset_balance(account: str, *, apply: bool = False) -> dict:
    """
    复位：将 account 知点余额恢复为 DEFAULT_BALANCE（造数用后必调）。
    """
    plan = {
        "op": "reset_balance",
        "site": AI_SITE,
        "account": account,
        "target_balance": DEFAULT_BALANCE,
        "applied": False,
    }
    if apply:
        _apply_reset_balance(account)
        plan["applied"] = True
    return plan


def _fmt_plan(plan: dict) -> str:
    return (
        f"  操作={plan['op']} 站点={plan['site']} 账号={plan['account']} "
        f"目标余额={plan['target_balance']} 已执行={plan['applied']}"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="AI 知点余额造数/复位（默认 dry-run，真实写需 .cn 接口+用户确认）"
    )
    parser.add_argument("--account", required=True, help="目标账号（手机号）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--balance", type=int, help="将余额置为该值（造数）")
    group.add_argument("--reset", action="store_true", help="复位为默认余额")
    parser.add_argument(
        "--apply", action="store_true",
        help="真实执行写操作（需 .cn 造数接口 + 用户确认；当前接口缺口会报错）",
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="计划/结果写到此 UTF-8 文件（默认打印到 stdout）",
    )
    args = parser.parse_args(argv)

    out = []
    out.append("=" * 60)
    mode = "真实执行(--apply)" if args.apply else "dry-run（不写库）"
    out.append(f"  AI 知点余额造数/复位 —— 模式：{mode}")
    out.append("=" * 60)

    try:
        if args.reset:
            plan = reset_balance(args.account, apply=args.apply)
        else:
            plan = set_balance(args.account, args.balance, apply=args.apply)
        out.append("将要执行/已执行的造数计划：")
        out.append(_fmt_plan(plan))
        if not args.apply:
            out.append("")
            out.append("[dry-run] 未写库。带 --apply 才会真实造数，且：")
            out.append("  1) 须先补 .cn 知点造数接口（当前 TODO 未实现）；")
            out.append("  2) 须经用户确认（规则1：先打印计划确认后落库）；")
            out.append("  3) 造数后务必调 reset_balance 复位（细则E）。")
        rc = 0
    except CaozhuInterfaceMissing as exc:
        out.append("[阻断] 真实写路径不可用：")
        out.append(f"  {exc}")
        rc = 2

    out.append("=" * 60)
    report = "\n".join(out) + "\n"

    if args.report:
        from pathlib import Path
        Path(args.report).write_text(report, encoding="utf-8")
    else:
        try:
            sys.stdout.write(report)
        except UnicodeEncodeError:
            sys.stdout.write(
                "[提示] 终端编码无法输出中文，请用 --report <file> 写 UTF-8 文件后 Read\n"
            )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
