"""
3D模型详情页 - 提供模型详情页相关操作和充值弹窗处理
"""
from typing import Optional, List, Dict
from playwright.sync_api import Locator, Page

from pages.base_page import BasePage


class RechargePackageInfo:
    """
    充值套餐信息数据类
    """
    def __init__(self):
        self.package_name: str = ""
        self.price: str = ""
        self.discount: str = ""
        self.bonus_items: List[str] = []
        self.remark: str = ""
        self.actual_pay_price: str = ""
        self.actual_discount_amount: str = ""

    def __str__(self):
        return (f"套餐名称: {self.package_name}\n"
                f"价格: {self.price}\n"
                f"优惠: {self.discount}\n"
                f"加购福利: {', '.join(self.bonus_items)}\n"
                f"备注: {self.remark}\n"
                f"实际支付: {self.actual_pay_price}\n"
                f"优惠金额: {self.actual_discount_amount}")


class ModelDetailPage(BasePage):
    """3D模型详情页类 - 知末网3D模型详情页"""
    def __init__(
        self,
        page: Optional[Page] = None,
        auto_close_popups: bool = False
    ) -> None:
        """
        ModelDetailPage 初始化
        :param page: Playwright Page 对象，可选
        :param auto_close_popups: 初始化时是否自动关闭弹框，默认 False
        """
        super().__init__(page, "pages/elements/model_detail_elements.yaml", auto_close_popups)

    # ===== 页面操作方法 =====
    def goto_model_detail_page(self, url: str = "https://3d.znzmo.com/3dmoxing/1198790555.html?requestId=22a843f6-3354-4146-a7b2-23f5c56a2d3d") -> None:
        """访问3D模型详情页"""
        self.goto(url, close_popups_after_load=True, wait_state="networkidle")

    def click_recharge_button(self) -> None:
        """点击充值按钮"""
        self.get_locator("recharge_button").first.click(force=True)
        # 等待弹窗出现
        self.wait.wait_for_timeout(2000)

    def click_download_button(self) -> None:
        """点击充值按钮"""
        self.get_locator("download_btn").first.click(force=True)
        # 等待弹窗出现
        self.wait.wait_for_timeout(2000)

    def is_recharge_modal_visible(self) -> bool:
        """检查充值弹窗是否可见"""
        try:
            return self.get_locator("recharge_modal").is_visible()
        except Exception:
            return False

    def get_recharge_packages(self) -> List[RechargePackageInfo]:
        """
        获取所有充值套餐信息

        :return: 套餐信息列表
        """
        packages = []

        if not self.is_recharge_modal_visible():
            print("充值弹窗未显示")
            return packages

        try:
            # 等待套餐卡片加载
            self.get_locator("package_card").first.wait_for(state="visible", timeout=5000)
            package_cards = self.get_locator("package_card").all()

            print(f"找到了 {len(package_cards)} 个套餐卡片")

            for card in package_cards:
                package_info = RechargePackageInfo()
                card.click()
                self.wait.wait_for_timeout(1000)
                # 先从卡片本身获取套餐名称和价格
                try:
                    name_selector = self._elements.get("package_name", ".package-name")
                    name = card.locator(name_selector).inner_text(timeout=2000)
                    package_info.package_name = name.strip() if name else ""
                except Exception as e:
                    print(f"获取套餐名称失败: {e}")

                try:
                    price_selector = self._elements.get("package_price", ".package-price")
                    price = card.locator(price_selector).inner_text(timeout=2000)
                    package_info.price = price.strip() if price else ""
                except Exception as e:
                    print(f"获取价格失败: {e}")

                # 优惠信息（相对于 card 获取）
                try:
                    discount_selector = self._elements.get("package_discount", ".package-discount")
                    discount = card.locator(discount_selector).inner_text(timeout=2000)
                    package_info.discount = discount.strip() if discount else ""
                except Exception as e:
                    print(f"获取优惠信息失败: {e}")

                # 加购福利（从整个页面获取，点击后显示）
                try:
                    bonus_items = self.get_locator("bonus_item").all()
                    package_info.bonus_items = []
                    for item in bonus_items:
                        item_text = item.inner_text(timeout=1000).strip()
                        if item_text:
                            package_info.bonus_items.append(item_text)
                except Exception as e:
                    print(f"获取加购福利失败: {e}")

                # 套餐备注（从整个页面获取，点击后显示）
                try:
                    remark = self.get_locator("package_remark").first.inner_text(timeout=2000)
                    package_info.remark = remark.strip() if remark else ""
                except Exception as e:
                    print(f"获取套餐备注失败: {e}")

                # 获取弹窗的实际支付和优惠信息
                try:
                    actual_pay_price = self.get_locator("actual_pay_price").first.inner_text(timeout=2000)
                    actual_discount_amount = self.get_locator("actual_discount_amount").first.inner_text(timeout=2000)
                    package_info.actual_pay_price = actual_pay_price.strip() if actual_pay_price else ""
                    package_info.actual_discount_amount = actual_discount_amount.strip() if actual_discount_amount else ""
                except Exception as e:
                    print(f"获取套餐实际支付信息失败: {e}")

                packages.append(package_info)

        except Exception as e:
            print(f"获取套餐信息失败: {e}")

        return packages

    def print_package_info(self, packages: List[RechargePackageInfo]) -> None:
        """
        打印套餐信息
        """
        print(f"\n=== 共找到 {len(packages)} 个充值套餐 ===")
        for i, package in enumerate(packages, 1):
            print(f"\n--- 套餐 {i}: ---")
            print(package)

    def close_recharge_modal(self) -> None:
        """关闭充值弹窗"""
        close_btn = self.get_locator("modal_close")
        if close_btn.is_visible():
            close_btn.click(force=True)
            self.wait.wait_for_timeout(1000)

    # ===== 页面元素定位方法（从 YAML 读取） =====
    def recharge_button(self) -> Locator:
        return self.get_locator("recharge_button")

    def recharge_modal(self) -> Locator:
        return self.get_locator("recharge_modal")

    def modal_title(self) -> Locator:
        return self.get_locator("modal_title")

    def package_cards(self) -> Locator:
        return self.get_locator("package_card")

    def modal_close(self) -> Locator:
        return self.get_locator("modal_close")
