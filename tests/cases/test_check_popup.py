"""
测试弹框是否在默认状态下弹出的用例
"""
import pytest
from playwright.sync_api import expect
from pages.methods.home_page import HomePage
from pages.methods.login_page import LoginPage


class TestPopupDefaultDisplay:
    """测试弹框默认显示状态"""

    @pytest.mark.quick
    @pytest.mark.smoke
    @pytest.mark.popup
    @pytest.mark.ui
    def test_homepage_popup_default_display(self, page):
        """
        测试首页在默认状态下是否弹出弹框
        要点：不自动关闭弹框，直接检查弹框存在
        """
        print("=== 测试首页弹框默认显示状态 ===")

        # 使用默认方式初始化，不自动关闭弹框
        home_page = HomePage(page)

        # 访问页面，也不关闭弹框
        home_page.goto(
            "https://www.znzmo.com/?from=personalCenter",
            close_popups_after_load=False,
            wait_state="networkidle"
        )

        # 等待一段时间让弹框加载
        home_page.wait.wait_for_timeout(2000)

        # 检查可能的弹框选择器
        popup_selectors = [
            ".ant-modal",
            ".modal",
            ".popup",
            ".dialog",
            "[role='dialog']"
        ]

        found_popup = False
        popup_detailed_info = []

        print("\n开始检查弹框...")

        for selector in popup_selectors:
            try:
                popup_elements = home_page.page.locator(selector)
                count = popup_elements.count()

                if count > 0:
                    found_popup = True
                    popup_detailed_info.append(f"选择器: {selector}")
                    popup_detailed_info.append(f"发现元素数量: {count}")

                    # 检查每个弹框是否可见
                    for i in range(count):
                        element = popup_elements.nth(i)
                        is_visible = element.is_visible(timeout=500)
                        if is_visible:
                            popup_detailed_info.append(f"  元素 {i}: 可见")
                            # 尝试获取弹框的文本内容
                            try:
                                text = element.inner_text(timeout=1000)
                                if text:
                                    popup_detailed_info.append(f"  内容预览: {text[:100]}...")
                            except:
                                pass
                        else:
                            popup_detailed_info.append(f"  元素 {i}: 不可见")
            except Exception as e:
                popup_detailed_info.append(f"选择器 {selector} 检查异常: {e}")
                continue

        # 额外检查常见的关闭按钮（间接判断弹框是否存在）
        close_button_selectors = [
            ".ant-modal-close",
            "button[class*='close']",
            "button.ant-modal-close",
            ".close-btn",
            "text=关闭",
            "text=×"
        ]

        close_buttons_found = []
        for selector in close_button_selectors:
            try:
                close_btn = home_page.page.locator(selector).first
                if close_btn.is_visible(timeout=500):
                    close_buttons_found.append(selector)
            except:
                continue

        # 输出结果
        print("\n" + "=" * 60)
        print("弹框检查结果:")
        print("=" * 60)

        if found_popup:
            print("✅ 检测到弹框存在!")
            print("\n详细信息:")
            for info in popup_detailed_info:
                print(f"  {info}")

            if close_buttons_found:
                print(f"\n发现的关闭按钮选择器: {close_buttons_found}")

            # 截图保存
            screenshot_path = "reports/screenshots/popup_detected.png"
            from pathlib import Path
            Path("reports/screenshots").mkdir(parents=True, exist_ok=True)
            home_page.page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n弹框截图已保存: {screenshot_path}")
        else:
            print("❌ 未检测到弹框")

            if close_buttons_found:
                print(f"\n但发现了关闭按钮: {close_buttons_found}")

            # 截图保存
            screenshot_path = "reports/screenshots/no_popup_detected.png"
            from pathlib import Path
            Path("reports/screenshots").mkdir(parents=True, exist_ok=True)
            home_page.page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n页面截图已保存: {screenshot_path}")

        print("=" * 60 + "\n")

        # 返回结果供参考
        return {
            "popup_found": found_popup,
            "popup_details": popup_detailed_info,
            "close_buttons": close_buttons_found
        }

    @pytest.mark.popup
    @pytest.mark.ui
    def test_login_page_popup_default_display(self, page):
        """
        测试登录页面前置弹框检查
        """
        print("\n=== 测试登录页面弹框默认显示状态 ===")

        login_page = LoginPage(page)
        login_page.goto(
            "https://www.znzmo.com/?from=personalCenter",
            close_popups_after_load=False,
            wait_state="networkidle"
        )

        login_page.wait.wait_for_timeout(2000)

        # 截图
        screenshot_path = "reports/screenshots/login_page_before_close.png"
        from pathlib import Path
        Path("reports/screenshots").mkdir(parents=True, exist_ok=True)
        login_page.page.screenshot(path=screenshot_path)
        print(f"登录页面截图已保存: {screenshot_path}")

        # 检查是否有弹框
        popup_found = False
        popup_selectors = [".ant-modal", ".modal", ".popup"]
        for selector in popup_selectors:
            try:
                if login_page.page.locator(selector).first.is_visible(timeout=500):
                    popup_found = True
                    print(f"检测到弹框: {selector}")
                    break
            except:
                continue

        if not popup_found:
            print("登录页面未检测到弹框")

        return popup_found


if __name__ == "__main__":
    print("直接运行弹框检查用例...")
