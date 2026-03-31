import time
from typing import Optional

from playwright.sync_api import Locator
from playwright.sync_api import Page

from core.base_page import BasePage


class LoginPage(BasePage):
    def __init__(
        self,
        page: Optional[Page] = None,
        auto_close_popups: bool = False
    ) -> None:
        """
        LoginPage 初始化
        :param page: Playwright Page 对象，可选
        :param auto_close_popups: 初始化时是否自动关闭弹框，默认 False
        """
        super().__init__(page, "pages/elements/login_page_elements.yaml", auto_close_popups)

    @classmethod
    def with_popup_handling(cls, page: Optional[Page] = None) -> "LoginPage":
        """工厂方法：创建会自动关闭弹框的 LoginPage"""
        return cls(page=page, auto_close_popups=True)

    @classmethod
    def without_popup_handling(cls, page: Optional[Page] = None) -> "LoginPage":
        """工厂方法：创建不自动关闭弹框的 LoginPage"""
        return cls(page=page, auto_close_popups=False)

    # ===== 简化版登录流程 - 知末网专用 =====
    def login_with(self, username: str, password: str) -> None:
        """知末网简化版登录流程"""
        print("=== 开始知末网登录流程 ===")

        # 1. 尝试关闭所有可能的弹窗（使用 BasePage 封装的方法）
        print("1. 尝试关闭弹窗...")
        closed_count = self.close_all_popups()
        if closed_count > 0:
            print(f"   - 成功关闭 {closed_count} 个弹窗")
        time.sleep(1)

        # 2. 点击登录|注册按钮
        print("2. 点击登录|注册...")
        try:
            login_register_btn = self.page.locator("text=登录|注册").first
            login_register_btn.click(force=True)
        except:
            login_register_btn = self.page.locator("a").filter(has_text="登录|注册").first
            login_register_btn.click(force=True)
        time.sleep(2)

        # 3. 直接点击手机按钮
        print("3. 点击手机按钮...")
        try:
            phone_tab = self.page.locator("text=手机").first
            if phone_tab.is_visible():
                phone_tab.click(force=True)
                time.sleep(1)
        except:
            pass

        # 4. 切换到账号密码登录
        print("4. 切换到账号密码登录...")
        login_options = ["账号密码登录", "密码登录"]
        for option_text in login_options:
            try:
                option = self.page.locator(f"text={option_text}").first
                if option.is_visible():
                    print(f"   - 找到并点击: '{option_text}'")
                    option.click(force=True)
                    time.sleep(1)
                    break
            except:
                continue

        # 5. 填写账号密码
        print("5. 填写账号密码...")
        try:
            phone_input = self.page.locator('input[placeholder="请输入手机号"]').first
            if phone_input.is_visible():
                phone_input.fill(username)
            pwd_input = self.page.locator('input[placeholder="请输入密码"]').first
            if pwd_input.is_visible():
                pwd_input.fill(password)
        except:
            pass
        time.sleep(0.5)

        # 6. 点击登录按钮
        print("6. 点击登录按钮...")
        login_btn = None
        login_btn_texts = ["登录/注册", "登录"]
        for btn_text in login_btn_texts:
            try:
                btn = self.page.locator(f"text={btn_text}").filter(visible=True).first
                if btn.is_visible():
                    login_btn = btn
                    print(f"   - 找到登录按钮: '{btn_text}'")
                    break
            except:
                continue

        if login_btn:
            login_btn.click(force=True)
            time.sleep(2)
            print("=== 登录流程执行完成 ===")
        else:
            print("⚠️ 未找到登录按钮，但流程已完成")

    # ===== 其他用于架构测试的方法 =====
    def username_input(self) -> Locator:
        return self.wait_element_visible("username_input")

    def password_input(self) -> Locator:
        return self.wait_element_visible("password_input")

    def submit_button(self) -> Locator:
        return self.wait_element_visible("submit_button")

    def success_message_locator(self) -> Locator:
        return self.wait_element_visible("success_message")

    def input_username(self, username: str) -> None:
        self.fill_element("username_input", username)

    def input_password(self, password: str) -> None:
        self.fill_element("password_input", password)

    def click_submit(self) -> None:
        self.click_element("submit_button")

    def wait_until_ready(self) -> None:
        self.username_input()
        self.password_input()
        self.submit_button()

    def goto_login_page(self, url: str = "https://www.znzmo.com/?from=personalCenter") -> None:
        """访问登录页面，自动关闭弹框"""
        self.goto(url, close_popups_after_load=True)
        time.sleep(1)
