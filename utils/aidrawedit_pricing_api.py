# -*- coding: utf-8 -*-
"""AIDrawEdit 独立 API 定价验证脚本。

基于 UI 采集的实际场景，完全匹配 UI 测试覆盖范围。
预期价格和会员账号从 tests/data/aidrawedit_pricing_baseline.yaml 读取。

运行：
  python utils/aidrawedit_pricing_api.py                    # 全部领域
  python utils/aidrawedit_pricing_api.py --domain 1         # 只跑室内设计
  python utils/aidrawedit_pricing_api.py --domain 0 1       # 跑通用+室内
  python utils/aidrawedit_pricing_api.py --member 普通会员   # 指定会员
  python utils/aidrawedit_pricing_api.py --json              # JSON 输出

字段说明：
  subServiceType : 场景唯一标识（跨领域一致）
  workFlowType   : 0=标准模式, 3=Nano Banana Pro, 4=GPT Image 2
  editAreaMode   : 0=非编辑模式, 1=编辑模式
  shadowType     : 光影类型（调光影场景需要，其他为 null）
  colorTab       : 颜色标签（换颜色场景需要，其他为 null）
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.pricing_helpers import api_login, fetch_price
from common.yaml_loader import load_yaml

# ── 加载基准数据 ─────────────────────────────────────────────────────────────
_BASELINE_PATH = "tests/data/aidrawedit_pricing_baseline.yaml"
_baseline = load_yaml(_BASELINE_PATH)
if not _baseline:
    raise FileNotFoundError(f"基准文件未找到: {_BASELINE_PATH}")

MEMBERS = _baseline.get("members", {})
SCENES_YAML = _baseline.get("scenes", {})
DOMAINS_YAML = _baseline.get("domains", {})

# ── 场景定义（元信息） ───────────────────────────────────────────────────────
# 从 YAML 构建，补充 YAML 中没有的字段
SCENES = {}
for sst, info in SCENES_YAML.items():
    models = info.get("models", [0])
    extra = info.get("extra", {})
    SCENES[sst] = {
        "name": info["name"],
        "models": [(wft, {0: "标准模式", 3: "Nano Banana Pro", 4: "GPT Image 2", 6: "Seedream 5 Pro"}.get(wft, f"wft{wft}")) for wft in models],
        "extra": extra,
    }

# ── 领域定义（从 YAML 构建，存储原始价格数据） ──────────────────────────────
DOMAINS = {}
RAW_PRICES = {}  # {domain_val: {key_str: {member: {peak: X, off_peak: Y}}}}
for dv, dinfo in DOMAINS_YAML.items():
    DOMAINS[dv] = {
        "name": dinfo["name"],
        "scenes": dinfo.get("scenes", []),
    }
    RAW_PRICES[dv] = dinfo.get("prices", {})


def get_expected(domain_val, sst, wft, edit_area, member, period="peak"):
    """从 YAML 原始数据中按会员名和时段读取预期值。"""
    key = f"{domain_val}_{sst}_{wft}_{edit_area}"
    member_prices = RAW_PRICES.get(domain_val, {}).get(key, {})
    tier_data = member_prices.get(member, {})
    if isinstance(tier_data, dict):
        val = tier_data.get(period)
        return val if val is not None else tier_data.get("peak")
    return None

# 模型名映射
MODEL_NAMES = {0: "标准模式", 3: "Nano Banana Pro", 4: "GPT Image 2"}

# editAreaMode 映射
EDIT_AREA_NAMES = {0: "非编辑", 1: "编辑"}


def build_params(domain_val, sst, wft, edit_area, extra):
    """构建 API 请求参数。"""
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
    return params


def main():
    parser = argparse.ArgumentParser(description="AIDrawEdit API 定价验证")
    parser.add_argument("--member", default="新钻石会员", help="会员账号")
    parser.add_argument("--domain", nargs="+", type=int, default=None,
                        help="指定领域（0=通用 1=室内 3=建筑 4=景观），不指定则全部")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--period", default="peak", choices=["peak", "normal", "off_peak"],
                        help="当前时段：peak=高峰, normal=平峰, off_peak=低谷")
    args = parser.parse_args()

    # 校验会员
    if args.member not in MEMBERS:
        print(f"错误: 未知会员 '{args.member}'，可选: {', '.join(MEMBERS.keys())}")
        sys.exit(1)

    domains_to_test = args.domain if args.domain else sorted(DOMAINS.keys())

    # 登录
    token = api_login(args.member)

    # 逐领域逐场景查询
    results = []
    for dv in domains_to_test:
        if dv not in DOMAINS:
            print(f"警告: 未知领域 domain={dv}，跳过")
            continue
        dcfg = DOMAINS[dv]
        dname = dcfg["name"]

        for sst in dcfg["scenes"]:
            scene = SCENES.get(sst)
            if not scene:
                continue
            for wft, model_name in scene["models"]:
                for edit_area in [0, 1]:
                    expected = get_expected(dv, sst, wft, edit_area, args.member, args.period)
                    if expected is None:
                        continue

                    params = build_params(dv, sst, wft, edit_area, scene["extra"])

                    resp = fetch_price(token, params)
                    data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
                    amount = data.get("amount")
                    err = resp.get("error", {}).get("errorCode", "?")

                    match = "✓" if amount == expected else "✗"
                    results.append({
                        "domain": dv, "domain_name": dname,
                        "sst": sst, "scene": scene["name"],
                        "model": model_name, "wft": wft,
                        "edit_area": edit_area, "edit_area_name": EDIT_AREA_NAMES[edit_area],
                        "expected": expected, "actual": amount,
                        "match": match, "error": err,
                    })

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # 输出汇总
    period_names = {"peak": "高峰期", "normal": "平峰期", "off_peak": "低谷期"}
    lines = ["", "=" * 100, f"  AIDrawEdit API 定价验证 — {args.member} — {period_names.get(args.period, args.period)}", "=" * 100]

    passed = failed = 0
    current_domain = None
    for r in results:
        if r["domain"] != current_domain:
            current_domain = r["domain"]
            lines.append(f"\n  ── {r['domain_name']} (domain={r['domain']}) ──")
            lines.append(f"  {'场景':<12} {'模型':<18} {'模式':<8} {'预期':<6} {'实际':<6} {'状态'}")
            lines.append("  " + "-" * 60)

        actual_str = str(r["actual"]) if r["actual"] is not None else "-"
        lines.append(
            f"  {r['scene']:<12} {r['model']:<18} {r['edit_area_name']:<8} {r['expected']:<6} {actual_str:<6} {r['match']}"
        )
        if r["match"] == "✓":
            passed += 1
        else:
            failed += 1

    lines.append(f"\n  总计: {len(results)}条, ✓ {passed}, ✗ {failed}")
    lines.append("=" * 100)
    print("\n".join(lines))

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
