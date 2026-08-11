# -*- coding: utf-8 -*-
"""高峰期 AI 改图知点消耗查询脚本。

查询调氛围(635)、调光影(634)、换天气(606) 在不同领域、不同会员、不同模型下的
高峰期实际 API 返回知点数。

会员账号从 tests/data/aidrawedit_pricing_baseline.yaml 读取。

用法：
  python utils/query_peak_pricing.py                   # 全部会员
  python utils/query_peak_pricing.py --member 普通会员  # 只查普通会员
  python utils/query_peak_pricing.py --json             # JSON 输出
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.pricing_helpers import api_login, fetch_price
from common.yaml_loader import load_yaml

# ── 加载会员账号 ─────────────────────────────────────────────────────────────
_BASELINE_PATH = "tests/data/aidrawedit_pricing_baseline.yaml"
_baseline = load_yaml(_BASELINE_PATH)
if not _baseline:
    raise FileNotFoundError(f"基准文件未找到: {_BASELINE_PATH}")

MEMBERS = _baseline.get("members", {})

# ── 目标场景 ──────────────────────────────────────────────────────────
TARGET_SCENES = {
    "635": {"name": "调氛围", "extra": {}},
    "634": {"name": "调光影", "extra": {"shadowType": 2}},
    "606": {"name": "换天气", "extra": {}},
}

# ── 领域配置 ──────────────────────────────────────────────────────────
DOMAINS = {
    0: "通用设计",
    1: "室内设计",
    3: "建筑设计",
    4: "景观设计",
}

# 每个领域可用的场景和模型
DOMAIN_SCENE_MODELS = {
    0: {  # 通用设计
        "606": [(0, "标准模式"), (3, "Nano")],
    },
    1: {  # 室内设计
        "634": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
        "635": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
    },
    3: {  # 建筑设计
        "634": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
        "635": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
        "606": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
    },
    4: {  # 景观设计
        "634": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
        "635": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
        "606": [(0, "标准模式"), (3, "Nano"), (4, "GPT")],
    },
}


def query_price(token, domain_val, sst, wft, edit_area, extra):
    """调 API 查询价格。"""
    params = {
        "channel": "znzmo",
        "serviceType": "6",
        "subServiceType": sst,
        "workFlowType": wft,
        "domain": str(domain_val),
        "editAreaMode": edit_area,
        "shadowType": None,
        "colorTab": None,
    }
    params.update(extra)
    resp = fetch_price(token, params)
    data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
    return data.get("amount"), resp.get("error", {}).get("errorCode", "?")


def main():
    parser = argparse.ArgumentParser(description="高峰期 AI 改图知点消耗查询")
    parser.add_argument("--member", nargs="+", default=None, help="指定会员（可多个）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    members_to_test = args.member if args.member else list(MEMBERS.keys())

    # 校验会员
    for m in members_to_test:
        if m not in MEMBERS:
            print(f"错误: 未知会员 '{m}'，可选: {', '.join(MEMBERS.keys())}")
            sys.exit(1)

    results = []

    for member_name in members_to_test:
        try:
            token = api_login(member_name)
            print(f"[OK] {member_name} 登录成功")
        except Exception as e:
            print(f"[ERR] {member_name} 登录失败: {e}")
            continue

        for domain_val, domain_name in DOMAINS.items():
            scene_models = DOMAIN_SCENE_MODELS.get(domain_val, {})
            for sst, models in scene_models.items():
                scene_name = TARGET_SCENES[sst]["name"]
                extra = TARGET_SCENES[sst]["extra"]
                for wft, model_name in models:
                    for edit_area in [0, 1]:
                        edit_name = "编辑" if edit_area == 1 else "非编辑"
                        try:
                            amount, err = query_price(
                                token, domain_val, sst, wft, edit_area, extra
                            )
                        except Exception as e:
                            amount, err = None, str(e)

                        results.append({
                            "member": member_name,
                            "domain": domain_val,
                            "domain_name": domain_name,
                            "scene": scene_name,
                            "sst": sst,
                            "model": model_name,
                            "wft": wft,
                            "edit_mode": edit_name,
                            "amount": amount,
                            "error": err,
                        })

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # ── 输出汇总表 ───────────────────────────────────────────────────
    print("\n" + "=" * 110)
    print("  AI 改图知点消耗（调氛围 / 调光影 / 换天气）")
    print("=" * 110)

    seen = set()
    current_domain = None
    current_scene = None

    for r in results:
        row_key = (r["domain"], r["scene"], r["sst"], r["model"], r["wft"], r["edit_mode"])
        if row_key in seen:
            continue
        seen.add(row_key)

        if r["domain"] != current_domain:
            current_domain = r["domain"]
            current_scene = None
            print(f"\n  ┌─ {r['domain_name']} (domain={r['domain']}) ─────────────────────────────────────────────")

        if r["scene"] != current_scene:
            current_scene = r["scene"]
            print(f"  │")
            print(f"  │  【{r['scene']}】")
            header = f"  │  {'模型':<14} {'模式':<6}"
            for m in members_to_test:
                header += f" {m:>8}"
            print(header)
            print(f"  │  {'-' * (14 + 6 + 9 * len(members_to_test))}")

        matching = [x for x in results if (
            x["domain"] == r["domain"] and x["scene"] == r["scene"] and
            x["sst"] == r["sst"] and x["model"] == r["model"] and
            x["wft"] == r["wft"] and x["edit_mode"] == r["edit_mode"]
        )]
        line = f"  │  {r['model']:<14} {r['edit_mode']:<6}"
        for m in members_to_test:
            found = [x for x in matching if x["member"] == m]
            if found:
                val = found[0]["amount"]
                line += f" {val if val is not None else '-':>8}"
            else:
                line += f" {'N/A':>8}"
        print(line)

    print(f"  └───────────────────────────────────────────────────────────────────────────────")

    # ── 快速对比表 ──────────────────────────────────────────────────
    print(f"\n")
    print("=" * 90)
    print("  快速对比：标准模式 · 非编辑 · 各领域")
    print("=" * 90)

    header = f"  {'场景':<8} {'领域':<10}"
    for m in members_to_test:
        header += f" {m:>8}"
    print(header)
    print(f"  {'-' * (8 + 10 + 9 * len(members_to_test))}")

    for sst in ["635", "634", "606"]:
        scene_name = TARGET_SCENES[sst]["name"]
        for domain_val in [1, 3, 4, 0]:
            domain_name = DOMAINS[domain_val]
            models = DOMAIN_SCENE_MODELS.get(domain_val, {}).get(sst, [])
            std_models = [m for m in models if m[0] == 0]
            if not std_models:
                continue
            line = f"  {scene_name:<8} {domain_name:<10}"
            for m in members_to_test:
                found = [x for x in results if (
                    x["member"] == m and x["domain"] == domain_val and
                    x["sst"] == sst and x["wft"] == 0 and x["edit_mode"] == "非编辑"
                )]
                if found:
                    val = found[0]["amount"]
                    line += f" {val if val is not None else '-':>8}"
                else:
                    line += f" {'-':>8}"
            print(line)

    print("=" * 90)


if __name__ == "__main__":
    main()
