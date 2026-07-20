# -*- coding: utf-8 -*-
"""调试换颜色场景的模型切换问题。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from playwright.sync_api import sync_playwright
from common.pricing_helpers import api_login, inject_cookie, parse_price
from pages.methods.aidrawedit_pricing_page import AIDrawEditPricingPage, DOMAINS

_MEMBER = "新钻石会员"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        token = api_login(_MEMBER)
        inject_cookie(page, token)

        pp = AIDrawEditPricingPage(page, auto_close_popups=False)
        pp.goto()
        pp.upload_image()
        pp.enable_api_intercept()

        # 切换到室内设计
        pp.switch_domain(0)

        # 选择换颜色场景
        print("\n=== 选择换颜色场景 ===")
        result = pp.select_scene_safe("换颜色")
        print(f"select_scene_safe 结果: {result}")

        # 涂抹进入编辑模式
        print("\n=== 涂抹进入编辑模式 ===")
        pp.paint_on_canvas()

        # 重新选择换颜色
        print("\n=== 重新选择换颜色 ===")
        result = pp.select_scene_safe("换颜色")
        print(f"select_scene_safe 结果: {result}")

        # 获取当前模型列表
        print("\n=== 获取模型列表 ===")
        models = pp.get_model_options()
        print(f"模型列表: {models}")

        # 逐个切换模型并获取价格
        for model_name in models:
            print(f"\n=== 切换到: {model_name} ===")
            pp.switch_model(model_name)
            page.wait_for_timeout(1000)

            # 获取当前激活的模型
            active_model = page.evaluate("""() => {
                const btn = document.querySelector('[class*="modeSelectBtn"]');
                return btn ? btn.innerText.trim() : 'unknown';
            }""")
            print(f"当前激活模型(页面显示): {active_model}")

            price = pp.get_current_price()
            price_value = parse_price(price)
            print(f"价格: {price} ({price_value})")

            # 检查API响应
            if pp._api_captured:
                last = pp._api_captured[-1]
                resp = last.get("response_body") or {}
                data = (resp.get("data") or {}) if isinstance(resp, dict) else None
                api_amount = data.get("amount") if data else None
                req_body = last.get("request_body") or {}
                print(f"API amount: {api_amount}")
                print(f"API workFlowType: {req_body.get('workFlowType')}")

        browser.close()

if __name__ == "__main__":
    main()
