# -*- coding: utf-8 -*-
"""主流程产品定价独立 API 验证脚本。

覆盖产品线：
  1. Agent模式/智能生图（1701）- GPT Image 2 / Nano Banana Pro / Nano Banana 2
  2. 精准渲染（1601）- 标准模式 / 思考模式 / Nano Banana Pro
  3. 创作渲染（1602）- 标准模式 / Nano Banana Pro
  4. 效果图美化（1603）- Nano Banana Pro
  5. 平面填彩（1604）- 标准模式 / Nano Banana Pro / GPT Image 2
  6. 实景改造（1606）- 标准模式 / Nano Banana Pro
  7. 全景渲染（1612）- 标准模式 / Nano Banana Pro
  8. 图转CAD（1614）- 标准模式
  9. 生成历史下载 - 超清原图Pro / 超清修复 / 下载PSD

预期价格和会员账号从 tests/data/pricing_baseline.yaml 读取。

运行：
  python utils/main_products_pricing_api.py                      # 全部产品
  python utils/main_products_pricing_api.py --product agent      # 只跑 Agent 模式
  python utils/main_products_pricing_api.py --product precision  # 只跑精准渲染
  python utils/main_products_pricing_api.py --member 普通会员     # 指定会员
  python utils/main_products_pricing_api.py --json               # JSON 输出
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.pricing import get_member_account, _load as load_baseline
from common.pricing_helpers import api_login, fetch_price

# ── 加载基准数据 ─────────────────────────────────────────────────────────────
_baseline = load_baseline()
MEMBERS = _baseline.get("members", {})
PRICING = _baseline.get("pricing", {})

# ── 产品线定义 ──────────────────────────────────────────────────────────────
# 每个产品线: name, api_params, 需要的 member × combination 组合
PRODUCT_LINES = {
    "agent": {
        "name": "Agent模式/智能生图",
        "combinations": {
            "GPT Image 2":    {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 4},
            "Nano Banana Pro": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 1},
            "Nano Banana 2":   {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 3},
        },
    },
    "precision": {
        "name": "精准渲染",
        "combinations": {
            "标准模式": {"serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2},
            "思考模式": {"channel": "znzmo", "serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": 1},
            "Nano Banana Pro": {"serviceType": "16", "subServiceType": "1601", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2},
        },
    },
    "idea": {
        "name": "创作渲染",
        "combinations": {
            "标准模式": {"serviceType": "16", "subServiceType": "1602", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
            "Nano Banana Pro": {"serviceType": "16", "subServiceType": "1602", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2},
        },
    },
    "enhancement": {
        "name": "效果图美化",
        "combinations": {
            "Nano Banana Pro": {"serviceType": "16", "subServiceType": "1603", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2},
        },
    },
    "floor_plan": {
        "name": "平面填彩",
        "combinations": {
            "标准模式": {"serviceType": "16", "subServiceType": "1604", "workFlowType": 2, "batchSize": 2, "pictureQuality": 0},
            "Nano Banana Pro": {"serviceType": "16", "subServiceType": "1604", "workFlowType": 3},
            "GPT Image 2":    {"serviceType": "16", "subServiceType": "1604", "workFlowType": 4},
        },
    },
    "insitu": {
        "name": "实景改造",
        "combinations": {
            "标准模式": {"serviceType": "16", "subServiceType": "1606", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
            "Nano Banana Pro": {"serviceType": "16", "subServiceType": "1606", "workFlowType": 3},
        },
    },
    "panoramic": {
        "name": "全景渲染",
        "combinations": {
            "标准模式": {"serviceType": "16", "subServiceType": "1612", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2},
            "Nano Banana Pro": {"serviceType": "16", "subServiceType": "1612", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2},
        },
    },
    "cad": {
        "name": "图转CAD",
        "combinations": {
            "标准模式": {"channel": "", "serviceType": "16", "subServiceType": "1614", "workFlowType": 0, "batchSize": 1, "pictureQuality": 0, "referenceImg": "", "sceneName": [], "deepMode": None},
        },
    },
    "history": {
        "name": "生成历史下载",
        "combinations": {
            "超清原图Pro": {"channel": "4kfix", "baseImageId": 20017777},
            "超清修复":    {"channel": "4k", "baseImageId": 20017777},
            "下载PSD":     {"channel": "znzmo", "serviceType": "6", "subServiceType": "638", "workFlowType": 4, "domain": "1", "editAreaMode": 0},
        },
    },
}

# product_key → pricing_baseline.yaml 中的 product 名
_PRODUCT_TO_PRICING_KEY = {
    "agent": "Agent模式",
    "precision": "精准渲染",
    "idea": "创作渲染",
    "enhancement": "效果图美化",
    "floor_plan": "平面填彩",
    "insitu": "实景改造",
    "panoramic": "全景渲染",
    "cad": "图转CAD",
    "history": "生成历史下载",
}


def get_expected(product_key, combination, member, period="peak"):
    """从 pricing_baseline.yaml 获取预期价格，按指定时段读取。"""
    pricing_key = _PRODUCT_TO_PRICING_KEY.get(product_key)
    if not pricing_key:
        return None
    try:
        prices = PRICING[pricing_key][combination]["prices"][member]
        val = prices.get(period)
        return val if val is not None else prices.get("peak")
    except (KeyError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="主流程产品定价 API 验证")
    parser.add_argument("--member", nargs="+", default=None, help="会员（可多个，默认全部）")
    parser.add_argument("--product", nargs="+", default=None,
                        help="产品线（可多个：agent/precision/idea/enhancement/floor_plan/insitu/panoramic/cad/history）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--period", default="peak", choices=["peak", "normal", "off_peak"],
                        help="当前时段：peak=高峰, normal=平峰, off_peak=低谷")
    args = parser.parse_args()

    members_to_test = args.member if args.member else list(MEMBERS.keys())
    products_to_test = args.product if args.product else list(PRODUCT_LINES.keys())

    # 校验
    for m in members_to_test:
        if m not in MEMBERS:
            print(f"错误: 未知会员 '{m}'，可选: {', '.join(MEMBERS.keys())}")
            sys.exit(1)
    for p in products_to_test:
        if p not in PRODUCT_LINES:
            print(f"错误: 未知产品 '{p}'，可选: {', '.join(PRODUCT_LINES.keys())}")
            sys.exit(1)

    results = []

    for member_name in members_to_test:
        try:
            token = api_login(member_name)
            print(f"[OK] {member_name} 登录成功", file=sys.stderr)
        except Exception as e:
            print(f"[ERR] {member_name} 登录失败: {e}", file=sys.stderr)
            continue

        for product_key in products_to_test:
            pline = PRODUCT_LINES[product_key]
            for combo_name, params in pline["combinations"].items():
                expected = get_expected(product_key, combo_name, member_name, args.period)

                try:
                    resp = fetch_price(token, params)
                    data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
                    amount = data.get("amount")
                    err = resp.get("error", {}).get("errorCode", "?")
                except Exception as e:
                    amount, err = None, str(e)

                match = None
                if expected is not None and amount is not None:
                    match = "✓" if amount == expected else "✗"

                results.append({
                    "member": member_name,
                    "product": pline["name"],
                    "product_key": product_key,
                    "combination": combo_name,
                    "expected": expected,
                    "actual": amount,
                    "match": match,
                    "error": err,
                })

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # ── 输出汇总 ───────────────────────────────────────────────────
    print("\n" + "=" * 100)
    period_names = {"peak": "高峰期", "normal": "平峰期", "off_peak": "低谷期"}
    print(f"  主流程产品定价 API 验证 — {period_names.get(args.period, args.period)}")
    print("=" * 100)

    passed = failed = no_expected = 0
    current_product = None

    for r in results:
        if r["product_key"] != current_product:
            current_product = r["product_key"]
            print(f"\n  ── {r['product']} ──")
            header = f"  {'组合':<16} {'会员':<10} {'预期':<6} {'实际':<6} {'状态'}"
            print(header)
            print("  " + "-" * 50)

        expected_str = str(r["expected"]) if r["expected"] is not None else "-"
        actual_str = str(r["actual"]) if r["actual"] is not None else "-"
        if r["match"]:
            status = r["match"]
        elif r["expected"] is None:
            status = "·"
        else:
            status = "?"

        print(f"  {r['combination']:<16} {r['member']:<10} {expected_str:<6} {actual_str:<6} {status}")

        if r["match"] == "✓":
            passed += 1
        elif r["match"] == "✗":
            failed += 1
        else:
            no_expected += 1

    print(f"\n  总计: {len(results)}条, ✓ {passed}, ✗ {failed}, 无预期 {no_expected}")
    print("=" * 100)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
