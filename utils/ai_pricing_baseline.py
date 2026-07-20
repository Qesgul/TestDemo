# -*- coding: utf-8 -*-
"""
AI 绘图会员知点定价基准表生成器（260618 需求）

作用
----
将 PRD「二、知点定价调整 / 定价表」严格还原为结构化基准数据
`功能族 × 档位 × 时段 -> 预期知点`，作为「120 格逐格核对」的唯一数据源。

数据来源
--------
D:\\code\\testcase\\260618 AI绘图会员权益及知点定价调整\\
    260618 AI绘图会员权益及知点定价调整.md  （定价表 = 「二、知点定价调整」节）
本脚本内置的 PRICING 字典即按该表第 25-32 行逐格手工还原，数值未做任何推算。

副作用
------
零业务副作用。仅：
  - 读：无（基准值已内置常量，不回读 PRD，避免 md 表格解析歧义）
  - 写：一个数据 YAML（默认写到 PRD 同目录，可用 --out 改路径）
不写库 / 不写缓存 / 不切量 / 不登录 / 不碰生产代码。

执行约定
--------
  - 默认 dry-run：仅打印将生成的结构与统计，不落盘。
  - 显式带 --write 才真正写 YAML 文件。
  - 含中文输出统一写 UTF-8 文件再由调用方 Read（规避 Windows GBK）。

特殊枚举（不写成数字）
----------------------
  - "无法使用"：该档位该时段该功能不可用（如普通会员 banana2 / banana模式全时段、4K 普通高峰）
  - 0          ：免费（PRD 中标「免费」的格，统一存为整数 0，便于 0 扣断言）
  - 普通会员「精准渲染-标准模式」整体标 note: 仅老会员可用（值仍按 PRD 取 10）

用法
----
  python utils/ai_pricing_baseline.py            # dry-run，仅打印
  python utils/ai_pricing_baseline.py --write     # 写默认路径 YAML
  python utils/ai_pricing_baseline.py --write --out D:\\tmp\\x.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── 枚举常量（特殊格用它，不用裸数字） ──────────────────────────────────────────
UNAVAILABLE = "无法使用"   # 该格不可用
FREE = 0                   # 免费 -> 统一存 0

# 档位 / 时段固定顺序（用于稳定遍历与统计）
TIERS = ["普通", "黄金", "铂金", "钻石", "黑金"]
PERIODS = ["高峰", "平峰", "低谷"]

# ── 定价基准（严格按 PRD 定价表第 25-32 行还原；数值未推算） ──────────────────────
# 每个功能族 -> {档位: {时段: 值}}；值为 int 或 UNAVAILABLE。
# note 为该功能族的整体备注（如「仅老会员可用」），不影响逐格值。
PRICING: dict = {
    # 智能生图 banana2：普通三时段均无法使用；其余档位三时段同值
    "智能生图_banana2": {
        "note": "外部调用模型，受峰期影响较小",
        "values": {
            "普通": {"高峰": UNAVAILABLE, "平峰": UNAVAILABLE, "低谷": UNAVAILABLE},
            "黄金": {"高峰": 10, "平峰": 10, "低谷": 10},
            "铂金": {"高峰": 8, "平峰": 8, "低谷": 8},
            "钻石": {"高峰": 8, "平峰": 8, "低谷": 8},
            "黑金": {"高峰": 7, "平峰": 7, "低谷": 7},
        },
    },
    # banana模式（banana Pro / GPT Image 2）：普通三时段无法使用
    "banana模式_bananaPro_GPTImage2": {
        "note": "banana Pro 和 GPT Image 2",
        "values": {
            "普通": {"高峰": UNAVAILABLE, "平峰": UNAVAILABLE, "低谷": UNAVAILABLE},
            "黄金": {"高峰": 15, "平峰": 15, "低谷": 15},
            "铂金": {"高峰": 12, "平峰": 12, "低谷": 12},
            "钻石": {"高峰": 12, "平峰": 12, "低谷": 12},
            "黑金": {"高峰": 10, "平峰": 10, "低谷": 10},
        },
    },
    # 精准渲染-标准模式：普通会员仅老会员可用（值 10）；钻石/黑金低谷免费
    "精准渲染_标准模式": {
        "note": "普通会员中只有老会员可用",
        "values": {
            "普通": {"高峰": 10, "平峰": 10, "低谷": 10},
            "黄金": {"高峰": 8, "平峰": 6, "低谷": 6},
            "铂金": {"高峰": 6, "平峰": 6, "低谷": 3},
            "钻石": {"高峰": 6, "平峰": 4, "低谷": FREE},
            "黑金": {"高峰": 6, "平峰": 4, "低谷": FREE},
        },
    },
    # 精准渲染-思考模式：去除体验折扣，定价同 banana 模式
    "精准渲染_思考模式": {
        "note": "去除4知点体验折扣，定价同 banana 模式",
        "values": {
            "普通": {"高峰": 15, "平峰": 15, "低谷": 15},
            "黄金": {"高峰": 15, "平峰": 15, "低谷": 15},
            "铂金": {"高峰": 12, "平峰": 12, "低谷": 12},
            "钻石": {"高峰": 12, "平峰": 12, "低谷": 12},
            "黑金": {"高峰": 10, "平峰": 10, "低谷": 10},
        },
    },
    # AI改图-轻量（≤80s）：黄金及以上低谷免费
    "AI改图_轻量_le80s": {
        "note": "细节增强/高清放大/去水印/高清增强/换视角，≤80s",
        "values": {
            "普通": {"高峰": 5, "平峰": 5, "低谷": 5},
            "黄金": {"高峰": 3, "平峰": 2, "低谷": FREE},
            "铂金": {"高峰": 3, "平峰": 2, "低谷": FREE},
            "钻石": {"高峰": 3, "平峰": 2, "低谷": FREE},
            "黑金": {"高峰": 3, "平峰": 2, "低谷": FREE},
        },
    },
    # AI改图-重型（>80s）：钻石/黑金低谷免费（黄金/铂金低谷为 4，非免费）
    "AI改图_重型_gt80s": {
        "note": "局部重绘/换材质/换风格等，>80s",
        "values": {
            "普通": {"高峰": 10, "平峰": 10, "低谷": 10},
            "黄金": {"高峰": 6, "平峰": 5, "低谷": 4},
            "铂金": {"高峰": 6, "平峰": 5, "低谷": 4},
            "钻石": {"高峰": 6, "平峰": 5, "低谷": FREE},
            "黑金": {"高峰": 6, "平峰": 5, "低谷": FREE},
        },
    },
    # 标准功能（按张数定价，81-140s）：钻石/黑金低谷免费
    "标准功能_按张数": {
        "note": "效果图美化/平面填彩/全景渲染/实景改造/快速出图，81-140s",
        "values": {
            "普通": {"高峰": 8, "平峰": 8, "低谷": 8},
            "黄金": {"高峰": 4, "平峰": 3, "低谷": 2},
            "铂金": {"高峰": 4, "平峰": 3, "低谷": 2},
            "钻石": {"高峰": 4, "平峰": 3, "低谷": FREE},
            "黑金": {"高峰": 4, "平峰": 3, "低谷": FREE},
        },
    },
    # 4K生图：普通高峰无法使用、平低 6；钻石高峰 4、平/低免费；黑金全时段免费
    "4K生图": {
        "note": "新版高清下载；取消新用户免费体验次数",
        "values": {
            "普通": {"高峰": UNAVAILABLE, "平峰": 6, "低谷": 6},
            "黄金": {"高峰": 6, "平峰": 4, "低谷": 4},
            "铂金": {"高峰": 6, "平峰": 4, "低谷": 4},
            "钻石": {"高峰": 4, "平峰": FREE, "低谷": FREE},
            "黑金": {"高峰": FREE, "平峰": FREE, "低谷": FREE},
        },
    },
}

DEFAULT_OUT = Path(
    r"D:\code\testcase\260618 AI绘图会员权益及知点定价调整\ai_pricing_baseline.yaml"
)


# ── YAML 序列化（自实现，零依赖；中文不转义、值类型保真） ───────────────────────
def _fmt_value(v) -> str:
    """int -> 裸数字；字符串枚举 -> 带引号（避免 YAML 把中文当裸标量歧义）。"""
    if isinstance(v, bool):  # 防御：不期望出现 bool
        return str(v).lower()
    if isinstance(v, int):
        return str(v)
    return f'"{v}"'


def to_yaml(pricing: dict) -> str:
    lines = []
    lines.append("# AI 绘图会员知点定价基准表（自动生成，勿手改）")
    lines.append("# 来源：PRD「二、知点定价调整 / 定价表」逐格还原")
    lines.append("# 枚举：\"无法使用\"=不可用；0=免费")
    lines.append("# 档位顺序：" + " / ".join(TIERS) + "；时段顺序：" + " / ".join(PERIODS))
    lines.append("pricing:")
    for family, block in pricing.items():
        lines.append(f"  {family}:")
        note = block.get("note", "")
        lines.append(f'    note: "{note}"')
        lines.append("    values:")
        for tier in TIERS:
            tier_map = block["values"][tier]
            cells = ", ".join(
                f"{period}: {_fmt_value(tier_map[period])}" for period in PERIODS
            )
            lines.append(f"      {tier}: {{{cells}}}")
    return "\n".join(lines) + "\n"


# ── 自检统计 ──────────────────────────────────────────────────────────────────
def collect_stats(pricing: dict) -> dict:
    total = 0
    unavailable_cells = []
    free_cells = []
    for family, block in pricing.items():
        for tier in TIERS:
            for period in PERIODS:
                total += 1
                v = block["values"][tier][period]
                if v == UNAVAILABLE:
                    unavailable_cells.append(f"{family} / {tier} / {period}")
                elif v == FREE:
                    free_cells.append(f"{family} / {tier} / {period}")
    return {
        "families": len(pricing),
        "tiers": len(TIERS),
        "periods": len(PERIODS),
        "total_cells": total,
        "unavailable": unavailable_cells,
        "free": free_cells,
    }


def build_report(stats: dict, out_path: Path, written: bool) -> str:
    lines = []
    lines.append("=" * 56)
    lines.append("  AI 定价基准表生成 — 自检统计")
    lines.append("=" * 56)
    lines.append(
        f"功能族 {stats['families']} × 档位 {stats['tiers']} × 时段 {stats['periods']}"
        f" = 格子总数 {stats['total_cells']}"
    )
    lines.append("")
    lines.append(f"「无法使用」格（{len(stats['unavailable'])} 个）：")
    for c in stats["unavailable"]:
        lines.append(f"  - {c}")
    lines.append("")
    lines.append(f"「免费(0)」格（{len(stats['free'])} 个）：")
    for c in stats["free"]:
        lines.append(f"  - {c}")
    lines.append("")
    if written:
        lines.append(f"[已写入] {out_path}")
    else:
        lines.append(f"[dry-run] 未写盘。带 --write 才会写到：{out_path}")
    lines.append("=" * 56)
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AI 绘图会员知点定价基准表生成器")
    parser.add_argument(
        "--write", action="store_true", help="真正写 YAML（默认 dry-run 只打印）"
    )
    parser.add_argument(
        "--out", type=str, default=str(DEFAULT_OUT), help="输出 YAML 路径"
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="自检统计写到此 UTF-8 文件（默认打印到 stdout）",
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    stats = collect_stats(PRICING)
    yaml_text = to_yaml(PRICING)

    written = False
    if args.write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_text, encoding="utf-8")
        written = True

    report = build_report(stats, out_path, written)

    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
    else:
        # 含中文：stdout 可能 GBK，做容错（编码失败则提示走 --report 文件）
        try:
            sys.stdout.write(report)
        except UnicodeEncodeError:
            sys.stdout.write(
                "[提示] 终端编码无法输出中文，请用 --report <file> 写 UTF-8 文件后 Read\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
