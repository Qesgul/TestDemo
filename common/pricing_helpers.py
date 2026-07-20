# -*- coding: utf-8 -*-
"""定价测试公共辅助模块。

提供 API 登录、Cookie 注入、弹窗清理、价格接口调用、价格解析、结果保存等
公共功能，消除各测试脚本和 API 采集脚本中的重复代码。
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests as http_requests

# ── 常量（单一来源）──────────────────────────────────────────────
LOGIN_API = "https://api.znzmo.cn/login/loginByPsw"
PRICE_API = "https://api.znzmo.cn/ai/api/aiDrawCoin/aiDrawPrice"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".workflow" / "pricing-output"

# ── 弹窗清理 JS ─────────────────────────────────────────────────
JS_DISMISS_MODALS = """() => {
    document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
    document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
}"""


# ── 登录 ─────────────────────────────────────────────────────────
def api_login(member: str = "新钻石会员") -> str:
    """API 登录获取 SESSION cookie。

    :param member: 会员等级名（如 "新钻石会员"）
    :return: SESSION token 字符串
    :raises RuntimeError: 登录失败或无 SESSION cookie
    """
    from common.pricing import get_member_account

    account = get_member_account(member)
    if not account:
        raise RuntimeError(f"会员账号未配置: {member}")
    pwd_md5 = hashlib.md5(account["password"].encode()).hexdigest()
    resp = http_requests.get(
        LOGIN_API,
        params={"username": account["username"], "password": pwd_md5},
        timeout=15,
    )
    data = resp.json()
    if data.get("error", {}).get("errorCode") != "0":
        raise RuntimeError(f"API 登录失败: {data}")
    token = resp.cookies.get("SESSION")
    if not token:
        raise RuntimeError("登录成功但无 SESSION cookie")
    return token


# ── Cookie 注入 ──────────────────────────────────────────────────
def inject_cookie(page, token: str) -> None:
    """注入 SESSION cookie 到 playwright context。

    :param page: playwright Page 对象
    :param token: SESSION token
    """
    page.context.add_cookies([{
        "name": "SESSION", "value": token,
        "domain": ".znzmo.cn", "path": "/",
        "secure": True, "httpOnly": True,
    }])


# ── 弹窗清理 ─────────────────────────────────────────────────────
def dismiss_modals(page) -> None:
    """JS 移除 ant-modal 弹窗。"""
    page.evaluate(JS_DISMISS_MODALS)


# ── API 调用 ─────────────────────────────────────────────────────
def fetch_price(token: str, params: dict) -> dict:
    """调用 aiDrawPrice 接口。

    :param token: SESSION token
    :param params: 请求参数 dict
    :return: 接口返回 JSON
    """
    headers = {"Content-Type": "application/json", "Cookie": f"SESSION={token}"}
    resp = http_requests.post(PRICE_API, json=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── 价格解析 ─────────────────────────────────────────────────────
def parse_price(text: str) -> Optional[int]:
    """从价格文本解析整数。

    :param text: 价格文本（如 "8"、"8知点"、""）
    :return: 解析后的整数，无法解析返回 None
    """
    if not text:
        return None
    try:
        return int(text.strip())
    except ValueError:
        digits = "".join(c for c in text if c.isdigit())
        return int(digits) if digits else None


# ── 结果保存 ─────────────────────────────────────────────────────
def save_result(result: dict, prefix: str = "pricing", suffix: str = "") -> Path:
    """保存结果到 JSON。

    :param result: 结果字典
    :param prefix: 文件名前缀
    :param suffix: 文件名后缀
    :return: 保存的文件路径
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUTPUT_DIR / f"{prefix}-{stamp}{suffix}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
