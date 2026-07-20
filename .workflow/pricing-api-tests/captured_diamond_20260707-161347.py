"""
从浏览器捕获的 aiDrawPrice 接口测试脚本
生成时间: 2026-07-07 16:13:47
捕获账号: 钻石会员
原始请求数: 29, 去重后: 22
"""

import requests
import json
from datetime import datetime

# ==================== 配置 ====================

COOKIE_FILE = None  # 设为 None 则使用下方硬编码 cookie

# 钻石会员 SESSION cookie（从浏览器捕获）
USER_SESSIONS = {
    "钻石会员": "SESSION=<替换为实际cookie>",
}

FORCE_TIME_PERIOD = ""  # 留空自动判断

API_URL = "https://api.znzmo.cn/ai/api/aiDrawCoin/aiDrawPrice"

# ==================== 捕获的测试场景 ====================

TEST_SCENARIOS = [
    # --- 场景 1: SVC17-sub1701-ch=znzmo-bch1 ---
    # 捕获响应: amount=12, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC17-sub1701-ch=znzmo-bch1",
        "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 1},
        "captured_response": {
            "amount": 12,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 2: SVC16-sub-wf2 ---
    # 捕获响应: amount=12, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 12,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 3: SVC17-sub1701-ch=znzmo-bch4 ---
    # 捕获响应: amount=12, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC17-sub1701-ch=znzmo-bch4",
        "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 4},
        "captured_response": {
            "amount": 12,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 4: SVC17-sub1701-ch=znzmo-bch3 ---
    # 捕获响应: amount=8, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC17-sub1701-ch=znzmo-bch3",
        "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 3},
        "captured_response": {
            "amount": 8,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 5: SVC16-sub1601-wf2 ---
    # 捕获响应: amount=6, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1601-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": null},
        "captured_response": {
            "amount": 6,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 6: SVC16-sub1601-ch=znzmo-wf2-dm1 ---
    # 捕获响应: amount=12, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1601-ch=znzmo-wf2-dm1",
        "params": {"channel": "znzmo", "serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": 1},
        "captured_response": {
            "amount": 12,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 7: SVC16-sub1602-wf2 ---
    # 捕获响应: amount=16, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1602-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1602", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 16,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 8: SVC16-sub1603-wf2 ---
    # 捕获响应: amount=4, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1603-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1603", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": null},
        "captured_response": {
            "amount": 4,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 9: SVC16-sub1603-wf3 ---
    # 捕获响应: amount=15, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1603-wf3",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1603", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": null},
        "captured_response": {
            "amount": 15,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 10: SVC16-sub1604-wf2 ---
    # 捕获响应: amount=8, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1604-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1604", "workFlowType": 2, "batchSize": 2, "pictureQuality": 0},
        "captured_response": {
            "amount": 8,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 11: SVC16-sub1604-wf3 ---
    # 捕获响应: amount=15, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1604-wf3",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1604", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2},
        "captured_response": {
            "amount": 15,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 12: SVC16-sub1604-wf4 ---
    # 捕获响应: amount=15, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1604-wf4",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1604", "workFlowType": 4, "batchSize": 1, "pictureQuality": 2},
        "captured_response": {
            "amount": 15,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 13: SVC16-sub1606-wf2 ---
    # 捕获响应: amount=16, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1606-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1606", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 16,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 14: SVC16-sub1606-wf3 ---
    # 捕获响应: amount=15, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1606-wf3",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1606", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2},
        "captured_response": {
            "amount": 15,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 15: SVC16-sub1612-wf2 ---
    # 捕获响应: amount=4, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1612-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1612", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": null},
        "captured_response": {
            "amount": 4,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 16: SVC16-sub1612-wf3 ---
    # 捕获响应: amount=15, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1612-wf3",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1612", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": null},
        "captured_response": {
            "amount": 15,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 17: SVC16-sub1601-wf2 ---
    # 捕获响应: amount=6, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1601-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2},
        "captured_response": {
            "amount": 6,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 18: SVC16-sub1604-wf2 ---
    # 捕获响应: amount=16, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1604-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1604", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 16,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 19: SVC16-sub1607-wf2 ---
    # 捕获响应: amount=16, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1607-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1607", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 16,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 20: SVC16-sub1608-wf2 ---
    # 捕获响应: amount=16, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1608-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1608", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 16,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 21: SVC16-sub1609-wf2 ---
    # 捕获响应: amount=16, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1609-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1609", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0},
        "captured_response": {
            "amount": 16,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

    # --- 场景 22: SVC16-sub1610-wf2 ---
    # 捕获响应: amount=3, isFreeTry=False, freeCount=0, vipType=2, hourType=0
    {
        "name": "SVC16-sub1610-wf2",
        "params": {"channel": "", "serviceType": "16", "subServiceType": "1610", "workFlowType": 2, "batchSize": 1, "pictureQuality": 0},
        "captured_response": {
            "amount": 3,
            "isFreeTry": false,
            "freeCount": 0,
            "vipType": 2,
            "hourType": 0,
        },
        "expected": {
            "钻石会员": {}  # 需要手动填入期望值
        },
    },

]

# ==================== 测试执行 ====================

def call_api(session, params):
    headers = {"Content-Type": "application/json", "Cookie": session}
    try:
        response = requests.post(API_URL, json=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"    接口调用失败: {e}")
        return None


def main():
    print("=" * 80)
    print("捕获的 aiDrawPrice 接口测试 — 钻石会员")
    print("=" * 80)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"场景数: {len(TEST_SCENARIOS)}")
    print("=" * 80)
    print()

    active = list(USER_SESSIONS.keys())
    if not active:
        print("错误: 未配置 USER_SESSIONS")
        return
    vip = active[0]
    session = USER_SESSIONS[vip]
    print(f"测试身份: {vip}\n")

    passed = 0
    failed = 0
    observe = 0

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"【{i}】{scenario['name']}")
        result = call_api(session, scenario["params"])
        if not result:
            print("    ✗ 接口调用失败")
            failed += 1
            continue

        data = result.get("data", {})
        amount = data.get("amount")
        is_free = data.get("isFreeTry")
        free_count = data.get("freeCount")
        vip_type = data.get("vipType")
        hour_type = data.get("hourType")

        captured = scenario.get("captured_response", {})
        cap_amount = captured.get("amount")

        if amount == cap_amount:
            print(f"    ✓ 通过 | amount={amount} (与捕获一致)")
            passed += 1
        else:
            print(f"    ✗ 失败 | 捕获={cap_amount}, 实际={amount}")
            failed += 1

        print(f"      isFreeTry={is_free}, freeCount={free_count}, vipType={vip_type}, hourType={hour_type}")
        print()

    print("=" * 80)
    print(f"通过: {passed}, 失败: {failed}")
    print("=" * 80)


if __name__ == "__main__":
    main()
