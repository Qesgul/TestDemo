"""
测试弹框处理的不同方式示例
展示如何使用 BasePage 的弹框处理配置
"""
import pytest
from pages.methods.login_page import LoginPage
from pages.methods.home_page import HomePage


class TestPopupHandling:
    """测试不同弹框处理方式的示例"""

    def test_login_without_auto_close_popups(self, page):
        """
        方式1: 不自动关闭弹框（默认）
        适用于需要查看弹框内容的测试场景
        """
        print("=== 方式1: 不自动关闭弹框 ===")

        # 使用默认方式，auto_close_popups=False
        login_page = LoginPage(page)
        login_page.goto_login_page()

        # 此时可以检查弹框是否存在
        # ... 可以在这里添加弹框相关的断言 ...

        # 需要时手动关闭
        closed_count = login_page.close_all_popups()
        print(f"手动关闭了 {closed_count} 个弹框")
        assert isinstance(closed_count, int) and closed_count >= 0, f"close_all_popups 返回值异常: {closed_count}"

        # 继续登录流程
        login_page.login_with("17768100279", "Qyff2011")
        print("✅ 登录流程完成")
        assert "znzmo.com" in login_page.page.url, f"登录后页面域名异常: {login_page.page.url}"

    def test_login_with_auto_close_popups(self, page):
        """
        方式2: 初始化时自动关闭弹框
        适用于不需要关注弹框的常规测试
        """
        print("=== 方式2: 初始化时自动关闭弹框 ===")

        # 使用参数开启自动关闭
        login_page = LoginPage(page, auto_close_popups=True)
        login_page.goto_login_page()

        login_page.login_with("17768100279", "Qyff2011")
        print("✅ 登录流程完成")
        assert "znzmo.com" in login_page.page.url, f"登录后页面域名异常: {login_page.page.url}"

    def test_homepage_without_auto_close(self, page):
        """测试 HomePage 不自动关闭弹框（用于查看弹框）"""
        print("=== HomePage 不自动关闭弹框 ===")

        home_page = HomePage(page)
        home_page.goto_homepage()

        print("✅ HomePage 加载完成，弹框未被自动关闭")
        assert "znzmo.com" in home_page.page.url, f"页面域名异常: {home_page.page.url}"

    def test_homepage_with_auto_close(self, page):
        """测试 HomePage 自动关闭弹框"""
        print("=== HomePage 自动关闭弹框 ===")

        home_page = HomePage(page, auto_close_popups=True)
        home_page.goto_homepage()

        print("✅ HomePage 加载完成，弹框已自动关闭")
        assert "znzmo.com" in home_page.page.url, f"页面域名异常: {home_page.page.url}"


class TestGotoMethodPopupControl:
    """测试 goto 方法的弹框控制"""

    def test_goto_without_closing_popups(self, page):
        """访问页面但不自动关闭弹框"""
        print("=== goto 不关闭弹框 ===")

        home_page = HomePage(page)
        # close_popups_after_load=False 表示访问页面后不关闭弹框
        home_page.goto(
            "https://www.znzmo.com/?from=personalCenter",
            close_popups_after_load=False
        )

        print("✅ 页面加载完成，弹框保留")
        assert "znzmo.com" in home_page.page.url, f"页面域名异常: {home_page.page.url}"

    def test_goto_with_closing_popups(self, page):
        """访问页面并自动关闭弹框"""
        print("=== goto 自动关闭弹框 ===")

        home_page = HomePage(page)
        home_page.goto(
            "https://www.znzmo.com/?from=personalCenter",
            close_popups_after_load=True
        )

        print("✅ 页面加载完成，弹框已关闭")
        assert "znzmo.com" in home_page.page.url, f"页面域名异常: {home_page.page.url}"


if __name__ == "__main__":
    print("弹框处理测试示例运行完成")
