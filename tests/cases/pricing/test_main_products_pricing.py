# -*- coding: utf-8 -*-
"""主产品定价采集 - 整合测试套件

覆盖范围：
  1. Agent模式（GPT Image 2 / Nano Banana Pro / Nano Banana 2）
  2. 精准渲染（标准模式 / 思考模式 / Nano Banana Pro）
  3. 创作渲染（标准模式 / Nano Banana Pro）
  4. 效果图美化（标准模式 / Nano Banana Pro）
  5. 平面填彩（标准模式 / Nano Banana Pro / GPT Image 2）
  6. 实景改造（标准模式 / Nano Banana Pro）
  7. 全景渲染（标准模式 / Nano Banana Pro）
  8. 图转CAD（标准模式）
  9. 生成历史下载（超清原图 / 超清修复 / 下载PSD）

运行方式：
  # 运行全部
  pytest tests/cases/pricing/test_main_products_pricing.py --override-ini="addopts=-q -s --headed" -v

  # 运行指定产品
  pytest tests/cases/pricing/test_main_products_pricing.py -k "agent" --override-ini="addopts=-q -s --headed" -v
  pytest tests/cases/pricing/test_main_products_pricing.py -k "precision" --override-ini="addopts=-q -s --headed" -v
  pytest tests/cases/pricing/test_main_products_pricing.py -k "floor_plan" --override-ini="addopts=-q -s --headed" -v
  pytest tests/cases/pricing/test_main_products_pricing.py -k "cad" --override-ini="addopts=-q -s --headed" -v
  pytest tests/cases/pricing/test_main_products_pricing.py -k "history" --override-ini="addopts=-q -s --headed" -v
"""

import pytest
from datetime import datetime

from common.pricing import get_expected_price, get_member_account
from common.pricing_helpers import api_login, inject_cookie, fetch_price, save_result
from pages.methods.pricing_capture_page import PricingCapturePage
from pages.methods.precision_render_pricing_page import PrecisionRenderPricingPage
from pages.methods.ai_pricing_page import AIPricingPage

# 强制定价测试在同一 worker 串行执行
pytestmark = pytest.mark.xdist_group("pricing")

# 默认测试账号
_DEFAULT_MEMBER = "新钻石会员"

# ── API 场景定义 ──────────────────────────────────────────────────────────────

# Agent模式
AGENT_SCENARIOS = [
    {"name": "GPT Image 2", "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 4}},
    {"name": "Nano Banana Pro", "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 1}},
    {"name": "Nano Banana 2", "params": {"channel": "znzmo", "serviceType": "17", "subServiceType": "1701", "isIntelligentAgentTask": 1, "bananaChannel": 3}},
]

# 精准渲染
PRECISION_SCENARIOS = [
    {"name": "标准模式", "params": {"serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2}},
    {"name": "思考模式", "params": {"channel": "znzmo", "serviceType": "16", "subServiceType": "1601", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": 1}},
    {"name": "Nano Banana Pro", "params": {"serviceType": "16", "subServiceType": "1601", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2}},
]

# 创作渲染
IDEA_SCENARIOS = [
    {"name": "标准模式", "params": {"serviceType": "16", "subServiceType": "1602", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0}},
    {"name": "Nano Banana Pro", "params": {"serviceType": "16", "subServiceType": "1602", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2}},
]

# 效果图美化
ENHANCEMENT_SCENARIOS = [
    {"name": "标准模式", "params": {"channel": "", "serviceType": "16", "subServiceType": "1603", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2, "referenceImg": "", "sceneName": [], "deepMode": None}},
    {"name": "Nano Banana Pro", "params": {"serviceType": "16", "subServiceType": "1603", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2}},
]

# 平面填彩
FLOOR_PLAN_SCENARIOS = [
    {"name": "标准模式", "params": {"serviceType": "16", "subServiceType": "1604", "workFlowType": 2, "batchSize": 2, "pictureQuality": 0}},
    {"name": "Nano Banana Pro", "params": {"serviceType": "16", "subServiceType": "1604", "workFlowType": 3}},
    {"name": "GPT Image 2", "params": {"serviceType": "16", "subServiceType": "1604", "workFlowType": 4}},
]

# 实景改造
INSITU_SCENARIOS = [
    {"name": "标准模式", "params": {"serviceType": "16", "subServiceType": "1606", "workFlowType": 2, "batchSize": 4, "pictureQuality": 0}},
    {"name": "Nano Banana Pro", "params": {"serviceType": "16", "subServiceType": "1606", "workFlowType": 3}},
]

# 全景渲染
PANORAMIC_SCENARIOS = [
    {"name": "标准模式", "params": {"serviceType": "16", "subServiceType": "1612", "workFlowType": 2, "batchSize": 1, "pictureQuality": 2}},
    {"name": "Nano Banana Pro", "params": {"serviceType": "16", "subServiceType": "1612", "workFlowType": 3, "batchSize": 1, "pictureQuality": 2}},
]

# 图转CAD
CAD_SCENARIOS = [
    {"name": "标准模式", "params": {"channel": "", "serviceType": "16", "subServiceType": "1614", "workFlowType": 0, "batchSize": 1, "pictureQuality": 0, "referenceImg": "", "sceneName": [], "deepMode": None}},
]

# 生成历史下载定价（基于UI捕获的API参数）
# 注：这些场景需要通过UI测试捕获实际API参数后更新
HISTORY_DOWNLOAD_SCENARIOS = [
    {"name": "超清原图Pro", "params": {"channel": "4kfix", "baseImageId": 20017777}},
    {"name": "超清修复", "params": {"channel": "4k", "baseImageId": 20017777}},
    {"name": "下载PSD", "params": {"channel": "znzmo", "serviceType": "6", "subServiceType": "638", "workFlowType": 4, "domain": "1", "editAreaMode": 0}},
]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="class")
def pricing_session(request, browser):
    """Class 级登录 fixture：独立 context/page。"""
    member = getattr(request, "param", _DEFAULT_MEMBER)
    context = browser.new_context()
    page = context.new_page()
    token = api_login(member)
    inject_cookie(page, token)
    yield page, token, member
    page.close()
    context.close()


# ── Agent模式测试 ─────────────────────────────────────────────────────────────

class TestAgentPricing:
    """Agent模式定价采集。"""

    @pytest.mark.parametrize("scenario", AGENT_SCENARIOS, ids=[s["name"] for s in AGENT_SCENARIOS])
    @pytest.mark.core
    def test_agent_api(self, scenario, assertion):
        """API查询Agent模式价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"agent_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"agent_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 精准渲染测试 ─────────────────────────────────────────────────────────────

class TestPrecisionPricing:
    """精准渲染定价采集。"""

    @pytest.mark.parametrize("scenario", PRECISION_SCENARIOS, ids=[s["name"] for s in PRECISION_SCENARIOS])
    @pytest.mark.core
    def test_precision_api(self, scenario, assertion):
        """API查询精准渲染价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"precision_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"precision_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 创作渲染测试 ─────────────────────────────────────────────────────────────

class TestIdeaPricing:
    """创作渲染定价采集。"""

    @pytest.mark.parametrize("scenario", IDEA_SCENARIOS, ids=[s["name"] for s in IDEA_SCENARIOS])
    @pytest.mark.core
    def test_idea_api(self, scenario, assertion):
        """API查询创作渲染价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"idea_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"idea_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 效果图美化测试 ───────────────────────────────────────────────────────────

class TestEnhancementPricing:
    """效果图美化定价采集。"""

    @pytest.mark.parametrize("scenario", ENHANCEMENT_SCENARIOS, ids=[s["name"] for s in ENHANCEMENT_SCENARIOS])
    @pytest.mark.core
    def test_enhancement_api(self, scenario, assertion):
        """API查询效果图美化价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"enhancement_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"enhancement_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 平面填彩测试 ─────────────────────────────────────────────────────────────

class TestFloorPlanPricing:
    """平面填彩定价采集。"""

    @pytest.mark.parametrize("scenario", FLOOR_PLAN_SCENARIOS, ids=[s["name"] for s in FLOOR_PLAN_SCENARIOS])
    @pytest.mark.core
    def test_floor_plan_api(self, scenario, assertion):
        """API查询平面填彩价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"floor_plan_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"floor_plan_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 实景改造测试 ─────────────────────────────────────────────────────────────

class TestInsituPricing:
    """实景改造定价采集。"""

    @pytest.mark.parametrize("scenario", INSITU_SCENARIOS, ids=[s["name"] for s in INSITU_SCENARIOS])
    @pytest.mark.core
    def test_insitu_api(self, scenario, assertion):
        """API查询实景改造价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"insitu_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"insitu_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 全景渲染测试 ─────────────────────────────────────────────────────────────

class TestPanoramicPricing:
    """全景渲染定价采集。"""

    @pytest.mark.parametrize("scenario", PANORAMIC_SCENARIOS, ids=[s["name"] for s in PANORAMIC_SCENARIOS])
    @pytest.mark.core
    def test_panoramic_api(self, scenario, assertion):
        """API查询全景渲染价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"panoramic_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"panoramic_{scenario['name']}_amount_positive",
            message=f"{scenario['name']} 价格应为非负数，实际: {amount}",
        )


# ── 图转CAD测试 ─────────────────────────────────────────────────────────────

class TestCADPricing:
    """图转CAD定价采集。"""

    @pytest.mark.core
    def test_cad_ui(self, pricing_session, assertion):
        """UI采集图转CAD价格。"""
        page, token, member = pricing_session

        # 导航到图转CAD页面
        page.goto("https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=imageToCad", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)

        # 获取价格
        price_el = page.locator('[class*="zdIconText"]').first
        price_el.wait_for(state="visible", timeout=15000)
        price_text = price_el.text_content().strip()
        price_value = int(price_text) if price_text.isdigit() else None

        # 校验价格非空
        assertion.assert_true(
            price_text != "",
            name="cad_ui_price_not_empty",
            message="图转CAD价格不应为空",
        )

        # 校验价格为非负整数
        if price_value is not None:
            assertion.assert_true(
                price_value >= 0,
                name="cad_ui_price_valid",
                message=f"图转CAD价格应>=0，实际: {price_value}",
            )

        # 打印结果
        print(f"\n  图转CAD UI价格: {price_text} (会员: {member})")

    @pytest.mark.parametrize("scenario", CAD_SCENARIOS, ids=[s["name"] for s in CAD_SCENARIOS])
    @pytest.mark.core
    def test_cad_api(self, scenario, assertion):
        """API查询图转CAD价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"cad_{scenario['name']}_success",
        )
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"cad_{scenario['name']}_amount_valid",
            message=f"{scenario['name']} 价格应>=0，实际: {amount}",
        )

    @pytest.mark.core
    def test_cad_api_ui_consistency(self, pricing_session, assertion):
        """校验图转CAD的API与UI价格一致性。"""
        page, token, member = pricing_session

        # UI采集
        page.goto("https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=imageToCad", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        price_el = page.locator('[class*="zdIconText"]').first
        price_el.wait_for(state="visible", timeout=15000)
        price_text = price_el.text_content().strip()
        ui_price = int(price_text) if price_text.isdigit() else None

        # API查询
        api_resp = fetch_price(token, CAD_SCENARIOS[0]["params"])
        api_amount = api_resp.get("data", {}).get("amount") if isinstance(api_resp.get("data"), dict) else None

        # 一致性校验
        if ui_price is not None and api_amount is not None:
            assertion.assert_equal(
                api_amount, ui_price,
                name="cad_api_ui_consistency",
                message=f"API({api_amount}) 应与 UI({ui_price}) 一致",
            )

        # 打印结果
        print(f"\n  图转CAD一致性校验: UI={ui_price}, API={api_amount}, 会员={member}")


# ── 生成历史下载定价测试 ─────────────────────────────────────────────────────

class TestHistoryDownloadPricing:
    """生成历史页面下载定价采集。

    页面: https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=history
    场景: 非全景渲染/非图转CAD类型的图片，hover后右上角出现下载按钮，
          点击后弹窗包含：超清原图、超清修复、下载PSD。
          同时点击图片进入详情弹窗，右上角也有下载按钮，验证价格一致性。
    """

    HISTORY_URL = "https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=history"

    @pytest.mark.core
    def test_history_hover_download_capture(self, pricing_session, assertion):
        """UI采集：hover下载按钮的API请求参数捕获。"""
        page, token, member = pricing_session
        captured_apis = []

        # 启用API拦截
        def _handle_route(route):
            request = route.request
            response = route.fetch()
            try:
                body = response.json()
            except Exception:
                body = None
            entry = {
                "url": request.url,
                "method": request.method,
                "request_body": None,
                "response_body": body,
            }
            post_data = request.post_data
            if post_data:
                try:
                    import json
                    entry["request_body"] = json.loads(post_data)
                except Exception:
                    entry["request_body"] = post_data
            captured_apis.append(entry)
            route.fulfill(response=response)

        page.route("**/aiDrawPrice**", _handle_route)

        # 导航到生成历史页面
        page.goto(self.HISTORY_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)

        # 清理弹窗
        page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
        }""")

        # 查找非全景渲染/非图转CAD的图片卡片
        # 先尝试找到图片列表容器
        image_cards = page.locator('[class*="historyItem"], [class*="cardItem"], [class*="imageCard"]').all()
        if not image_cards:
            # 备用选择器
            image_cards = page.locator('[class*="card"], [class*="item"]').all()

        assertion.assert_true(
            len(image_cards) > 0,
            name="history_has_images",
            message="生成历史页面应有图片卡片",
        )

        if len(image_cards) == 0:
            print(f"\n  生成历史页面未找到图片卡片，URL: {page.url}")
            return

        # Hover第一个图片卡片，等待下载按钮出现
        first_card = image_cards[0]
        first_card.hover(timeout=5000)
        page.wait_for_timeout(1000)

        # 查找下载按钮（右上角）
        download_btn = page.locator('[class*="download"], [class*="Download"]').first
        if not download_btn.is_visible(timeout=3000):
            # 尝试其他选择器
            download_btn = page.locator('button:has-text("下载"), [title*="下载"]').first

        assertion.assert_true(
            download_btn.is_visible(timeout=3000),
            name="hover_download_btn_visible",
            message="hover后应显示下载按钮",
        )

        # 点击下载按钮
        download_btn.click(timeout=5000)
        page.wait_for_timeout(2000)

        # 查找下载弹窗中的选项
        download_options = {}
        option_selectors = [
            ('超清原图', '[class*="ultraHd"], [class*="original"], :text("超清原图")'),
            ('超清修复', '[class*="ultraRepair"], [class*="repair"], :text("超清修复")'),
            ('下载PSD', '[class*="psd"], [class*="PSD"], :text("下载PSD")'),
        ]

        for option_name, selector in option_selectors:
            try:
                option_el = page.locator(selector).first
                if option_el.is_visible(timeout=2000):
                    # 获取价格文本
                    price_text = option_el.text_content().strip()
                    download_options[option_name] = price_text
            except Exception:
                pass

        # 记录捕获的API
        api_count = len(captured_apis)
        print(f"\n  生成历史hover下载 - 会员: {member}")
        print(f"  捕获API数量: {api_count}")
        print(f"  下载选项: {download_options}")

        # 关闭弹窗
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # 保存捕获的API参数
        if captured_apis:
            from common.pricing_helpers import save_result
            save_result({
                "test": "history_hover_download",
                "member": member,
                "captured_apis": captured_apis,
                "download_options": download_options,
            }, prefix="history_hover_download")

    @pytest.mark.core
    def test_history_detail_download_capture(self, pricing_session, assertion):
        """UI采集：详情弹窗下载按钮的API请求参数捕获。"""
        page, token, member = pricing_session
        captured_apis = []

        # 启用API拦截
        def _handle_route(route):
            request = route.request
            response = route.fetch()
            try:
                body = response.json()
            except Exception:
                body = None
            entry = {
                "url": request.url,
                "method": request.method,
                "request_body": None,
                "response_body": body,
            }
            post_data = request.post_data
            if post_data:
                try:
                    import json
                    entry["request_body"] = json.loads(post_data)
                except Exception:
                    entry["request_body"] = post_data
            captured_apis.append(entry)
            route.fulfill(response=response)

        page.route("**/aiDrawPrice**", _handle_route)

        # 导航到生成历史页面
        page.goto(self.HISTORY_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)

        # 清理弹窗
        page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
        }""")

        # 查找图片卡片
        image_cards = page.locator('[class*="historyItem"], [class*="cardItem"], [class*="imageCard"]').all()
        if not image_cards:
            image_cards = page.locator('[class*="card"], [class*="item"]').all()

        assertion.assert_true(
            len(image_cards) > 0,
            name="history_detail_has_images",
            message="生成历史页面应有图片卡片",
        )

        if len(image_cards) == 0:
            return

        # 点击图片卡片，打开详情弹窗
        first_card = image_cards[0]
        first_card.click(timeout=5000)
        page.wait_for_timeout(2000)

        # 查找详情弹窗中的下载按钮
        detail_download_btn = page.locator('[class*="download"], [class*="Download"]').first
        if not detail_download_btn.is_visible(timeout=3000):
            detail_download_btn = page.locator('button:has-text("下载"), [title*="下载"]').first

        assertion.assert_true(
            detail_download_btn.is_visible(timeout=3000),
            name="detail_download_btn_visible",
            message="详情弹窗应显示下载按钮",
        )

        # 点击下载按钮
        detail_download_btn.click(timeout=5000)
        page.wait_for_timeout(2000)

        # 查找下载弹窗中的选项
        download_options = {}
        option_selectors = [
            ('超清原图', '[class*="ultraHd"], [class*="original"], :text("超清原图")'),
            ('超清修复', '[class*="ultraRepair"], [class*="repair"], :text("超清修复")'),
            ('下载PSD', '[class*="psd"], [class*="PSD"], :text("下载PSD")'),
        ]

        for option_name, selector in option_selectors:
            try:
                option_el = page.locator(selector).first
                if option_el.is_visible(timeout=2000):
                    price_text = option_el.text_content().strip()
                    download_options[option_name] = price_text
            except Exception:
                pass

        # 记录捕获的API
        api_count = len(captured_apis)
        print(f"\n  生成历史详情下载 - 会员: {member}")
        print(f"  捕获API数量: {api_count}")
        print(f"  下载选项: {download_options}")

        # 关闭弹窗
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # 保存捕获的API参数
        if captured_apis:
            from common.pricing_helpers import save_result
            save_result({
                "test": "history_detail_download",
                "member": member,
                "captured_apis": captured_apis,
                "download_options": download_options,
            }, prefix="history_detail_download")

    @pytest.mark.core
    def test_history_download_consistency(self, pricing_session, assertion):
        """校验hover下载和详情下载的价格一致性。"""
        page, token, member = pricing_session

        # 导航到生成历史页面
        page.goto(self.HISTORY_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)

        # 清理弹窗
        page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
        }""")

        # 查找图片卡片
        image_cards = page.locator('[class*="historyItem"], [class*="cardItem"], [class*="imageCard"]').all()
        if not image_cards:
            image_cards = page.locator('[class*="card"], [class*="item"]').all()

        if len(image_cards) == 0:
            print(f"\n  生成历史页面未找到图片卡片，跳过一致性校验")
            return

        # 1. Hover下载获取价格
        first_card = image_cards[0]
        first_card.hover(timeout=5000)
        page.wait_for_timeout(1000)

        hover_download_btn = page.locator('[class*="download"], [class*="Download"]').first
        if not hover_download_btn.is_visible(timeout=3000):
            hover_download_btn = page.locator('button:has-text("下载"), [title*="下载"]').first

        hover_prices = {}
        if hover_download_btn.is_visible(timeout=3000):
            hover_download_btn.click(timeout=5000)
            page.wait_for_timeout(2000)

            # 获取各选项价格
            for option_name in ['超清原图', '超清修复', '下载PSD']:
                try:
                    option_el = page.locator(f':text("{option_name}")').first
                    if option_el.is_visible(timeout=1000):
                        price_text = option_el.text_content().strip()
                        hover_prices[option_name] = price_text
                except Exception:
                    pass

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        # 2. 详情下载获取价格
        first_card.click(timeout=5000)
        page.wait_for_timeout(2000)

        detail_download_btn = page.locator('[class*="download"], [class*="Download"]').first
        if not detail_download_btn.is_visible(timeout=3000):
            detail_download_btn = page.locator('button:has-text("下载"), [title*="下载"]').first

        detail_prices = {}
        if detail_download_btn.is_visible(timeout=3000):
            detail_download_btn.click(timeout=5000)
            page.wait_for_timeout(2000)

            for option_name in ['超清原图', '超清修复', '下载PSD']:
                try:
                    option_el = page.locator(f':text("{option_name}")').first
                    if option_el.is_visible(timeout=1000):
                        price_text = option_el.text_content().strip()
                        detail_prices[option_name] = price_text
                except Exception:
                    pass

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        # 3. 一致性校验
        print(f"\n  生成历史下载一致性校验 - 会员: {member}")
        print(f"  Hover下载价格: {hover_prices}")
        print(f"  详情下载价格: {detail_prices}")

        for option_name in ['超清原图', '超清修复', '下载PSD']:
            hover_price = hover_prices.get(option_name)
            detail_price = detail_prices.get(option_name)
            if hover_price and detail_price:
                assertion.assert_equal(
                    hover_price, detail_price,
                    name=f"history_{option_name}_consistency",
                    message=f"{option_name} hover下载({hover_price})应与详情下载({detail_price})一致",
                )

    @pytest.mark.core
    def test_history_download_api_params(self, pricing_session, assertion):
        """验证下载选项的API请求参数。"""
        page, token, member = pricing_session
        captured_apis = []

        # 启用API拦截
        def _handle_route(route):
            request = route.request
            response = route.fetch()
            try:
                body = response.json()
            except Exception:
                body = None
            entry = {
                "url": request.url,
                "method": request.method,
                "request_body": None,
                "response_body": body,
            }
            post_data = request.post_data
            if post_data:
                try:
                    import json
                    entry["request_body"] = json.loads(post_data)
                except Exception:
                    entry["request_body"] = post_data
            captured_apis.append(entry)
            route.fulfill(response=response)

        page.route("**/aiDrawPrice**", _handle_route)

        # 导航到生成历史页面
        page.goto(self.HISTORY_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)

        # 清理弹窗
        page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
        }""")

        # 查找图片卡片
        image_cards = page.locator('[class*="historyItem"], [class*="cardItem"], [class*="imageCard"]').all()
        if not image_cards:
            image_cards = page.locator('[class*="card"], [class*="item"]').all()

        if len(image_cards) == 0:
            print(f"\n  生成历史页面未找到图片卡片，跳过API参数验证")
            return

        # Hover下载
        first_card = image_cards[0]
        first_card.hover(timeout=5000)
        page.wait_for_timeout(1000)

        download_btn = page.locator('[class*="download"], [class*="Download"]').first
        if not download_btn.is_visible(timeout=3000):
            download_btn = page.locator('button:has-text("下载"), [title*="下载"]').first

        if download_btn.is_visible(timeout=3000):
            download_btn.click(timeout=5000)
            page.wait_for_timeout(2000)

            # 点击各个下载选项，捕获API
            for option_name in ['超清原图', '超清修复', '下载PSD']:
                try:
                    option_el = page.locator(f':text("{option_name}")').first
                    if option_el.is_visible(timeout=1000):
                        api_before = len(captured_apis)
                        option_el.click(timeout=3000)
                        page.wait_for_timeout(2000)

                        # 检查是否捕获到新的API请求
                        new_apis = captured_apis[api_before:]
                        if new_apis:
                            last_api = new_apis[-1]
                            req_body = last_api.get("request_body", {})
                            resp_body = last_api.get("response_body", {})
                            amount = resp_body.get("data", {}).get("amount") if isinstance(resp_body.get("data"), dict) else None

                            print(f"\n  {option_name} API参数:")
                            print(f"    subServiceType: {req_body.get('subServiceType')}")
                            print(f"    workFlowType: {req_body.get('workFlowType')}")
                            print(f"    domain: {req_body.get('domain')}")
                            print(f"    editAreaMode: {req_body.get('editAreaMode')}")
                            print(f"    amount: {amount}")

                            # 校验API返回成功
                            assertion.assert_equal(
                                resp_body.get("error", {}).get("errorCode"), "0",
                                name=f"history_{option_name}_api_success",
                                message=f"{option_name} API应返回成功",
                            )

                            # 校验价格为正数
                            assertion.assert_true(
                                isinstance(amount, (int, float)) and amount >= 0,
                                name=f"history_{option_name}_amount_positive",
                                message=f"{option_name} 价格应为非负数，实际: {amount}",
                            )
                except Exception as e:
                    print(f"\n  {option_name} 点击失败: {e}")

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        # 保存捕获的API参数
        if captured_apis:
            from common.pricing_helpers import save_result
            save_result({
                "test": "history_download_api_params",
                "member": member,
                "captured_apis": captured_apis,
            }, prefix="history_download_api_params")

            print(f"\n  生成历史下载API参数已保存，共捕获 {len(captured_apis)} 个请求")


# ── 生成历史下载API测试 ─────────────────────────────────────────────────────

class TestHistoryDownloadAPI:
    """生成历史下载定价API测试。

    基于UI捕获的API参数，验证下载选项的价格。
    """

    @pytest.mark.parametrize("scenario", HISTORY_DOWNLOAD_SCENARIOS, ids=[s["name"] for s in HISTORY_DOWNLOAD_SCENARIOS])
    @pytest.mark.core
    def test_history_download_api(self, scenario, assertion):
        """API查询生成历史下载价格。"""
        token = api_login(_DEFAULT_MEMBER)
        resp = fetch_price(token, scenario["params"])
        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        amount = data.get("amount")
        is_free = data.get("isFreeTry", False)

        assertion.assert_equal(
            resp.get("error", {}).get("errorCode"), "0",
            name=f"history_{scenario['name']}_success",
        )
        # 免费试用时价格可以为0
        assertion.assert_true(
            isinstance(amount, (int, float)) and amount >= 0,
            name=f"history_{scenario['name']}_amount_valid",
            message=f"{scenario['name']} 价格应>=0，实际: {amount}",
        )

        status = " (免费试用)" if is_free else ""
        print(f"\n  {scenario['name']} API价格: {amount}知点{status} (会员: {_DEFAULT_MEMBER})")

    @pytest.mark.core
    def test_history_download_api_ui_consistency(self, pricing_session, assertion):
        """校验生成历史下载的API与UI价格一致性。"""
        page, token, member = pricing_session

        # 导航到生成历史页面
        page.goto("https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=history", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)

        # 清理弹窗
        page.evaluate("""() => {
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-root').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-mask').forEach(el => el.remove());
        }""")

        # 查找图片卡片
        image_cards = page.locator('[class*="historyItem"], [class*="cardItem"], [class*="imageCard"]').all()
        if not image_cards:
            image_cards = page.locator('[class*="card"], [class*="item"]').all()

        if len(image_cards) == 0:
            print(f"\n  生成历史页面未找到图片卡片，跳过API/UI一致性校验")
            return

        # Hover下载获取UI价格
        first_card = image_cards[0]
        first_card.hover(timeout=5000)
        page.wait_for_timeout(1000)

        download_btn = page.locator('[class*="download"], [class*="Download"]').first
        if not download_btn.is_visible(timeout=3000):
            download_btn = page.locator('button:has-text("下载"), [title*="下载"]').first

        ui_prices = {}
        if download_btn.is_visible(timeout=3000):
            download_btn.click(timeout=5000)
            page.wait_for_timeout(2000)

            # 获取各选项价格
            for option_name in ['超清原图', '超清修复', '下载PSD']:
                try:
                    option_el = page.locator(f':text("{option_name}")').first
                    if option_el.is_visible(timeout=1000):
                        price_text = option_el.text_content().strip()
                        # 提取数字价格
                        import re
                        price_match = re.search(r'(\d+)', price_text)
                        if price_match:
                            ui_prices[option_name] = int(price_match.group(1))
                except Exception:
                    pass

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        # API查询获取价格
        api_prices = {}
        for scenario in HISTORY_DOWNLOAD_SCENARIOS:
            resp = fetch_price(token, scenario["params"])
            data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
            amount = data.get("amount")
            if amount is not None:
                api_prices[scenario["name"]] = amount

        # 一致性校验
        print(f"\n  生成历史下载API/UI一致性校验 - 会员: {member}")
        print(f"  UI价格: {ui_prices}")
        print(f"  API价格: {api_prices}")

        for option_name in ['超清原图', '超清修复', '下载PSD']:
            ui_price = ui_prices.get(option_name)
            api_price = api_prices.get(option_name)
            if ui_price is not None and api_price is not None:
                assertion.assert_equal(
                    api_price, ui_price,
                    name=f"history_{option_name}_api_ui_consistency",
                    message=f"{option_name} API({api_price})应与UI({ui_price})一致",
                )
