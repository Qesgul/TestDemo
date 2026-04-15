from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RechargeBonusItem:
    """
    充值套餐的加购福利项目
    """
    title: str
    description: Optional[str] = None


@dataclass
class RechargePackageInfo:
    """
    充值套餐信息数据类
    """
    package_name: str
    price: str
    package_discount: str
    bonus_items: List[RechargeBonusItem] = field(default_factory=list)
    package_remark: Optional[str] = None
    actual_pay_price: Optional[str] = None
    actual_discount_amount: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "套餐名称": self.package_name,
            "价格": self.price,
            "套餐优惠": self.package_discount,
            "加购福利内容": [
                {"标题": item.title, "描述": item.description}
                for item in self.bonus_items
            ],
            "套餐备注": self.package_remark,
            "实际支付价格": self.actual_pay_price,
            "实际优惠金额": self.actual_discount_amount
        }

    def __str__(self):
        """字符串表示"""
        bonus_str = "\n".join(
            f"  - {item.title}" + (f": {item.description}" if item.description else "")
            for item in self.bonus_items
        )
        if self.bonus_items:
            bonus_content = f"\n{bonus_str}"
        else:
            bonus_content = ""

        return (
            f"套餐名称: {self.package_name}\n"
            f"价格: {self.price}\n"
            f"套餐优惠: {self.package_discount}\n"
            f"加购福利内容: {bonus_content}\n"
            f"套餐备注: {self.package_remark if self.package_remark else '无'}\n"
            f"实际支付价格: {self.actual_pay_price}\n"
            f"实际优惠金额: {self.actual_discount_amount}\n"
        )
