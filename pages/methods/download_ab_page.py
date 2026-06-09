"""下载确认弹窗 AB 实验 - Page Object。

继承 NonvipDownloadPage（再上溯 ModelDetailPage），复用：
  - click_download_button() / wait_for_download_dialog() / close_download_dialog()
  - get_total_amount_text() / get_discount_amount_text() / parse_zhibi()
  - mock_user_pay_identity(data_value)（VIP 身份 mock 兜底）

本类追加：
  - set_split_group()           全局切量：UPDATE user_group_common.radio + 清 Redis（机制见 utils/一键修改_任意切量分组.py）
  - clear_split_redis()         仅清切量 Redis 缓存
  - query_split_record()        查切量埋点表记录（表名/字段提测后回填）
  - get_detail_take_price_text()/has_detail_coupon_price()  详情页到手价 / 券后价探测
  - is_field_visible() 及一组语义化可见性方法（VIP立减/待激活/抵扣券/搭售区/不使用残留）
  - get_main_button_text()/get_bottom_bar_text()/has_bottom_cash()  按钮与底部条
  - get_activity_discount_text()/get_material_info()

⚠️ 需求未提测：实验态 selector 多为 TODO_SELECTOR（见 download_ab_elements.yaml）；
   切量名/radio 未配置时 set_split_group() 返回 False，用例据此 skip(待考虑)。
"""
from __future__ import annotations

import logging
from typing import Optional

from playwright.sync_api import Page

from common.yaml_loader import load_yaml
from pages.methods.nonvip_download_page import NonvipDownloadPage

_logger = logging.getLogger(__name__)

_AB_DATA_PATH = "tests/data/download_ab_data.yaml"


class DownloadAbPage(NonvipDownloadPage):
    """下载确认弹窗 AB 实验 - 基于 NonvipDownloadPage 扩展。"""

    # ── 唯一 URL 配置点：复用 su.znzmo.com 36知币 付费素材详情页 ─────────────────
    DEFAULT_URL = "https://su.znzmo.com/sumoxing/1200607583.html?collDownType=1"

    def __init__(self, page: Page, auto_close_popups: bool = False) -> None:
        super().__init__(page=page, auto_close_popups=auto_close_popups)
        # 追加 AB 专属 selector（覆盖同名 key；继承的弹窗 selector 不在此文件重复）
        ab_elements = load_yaml("pages/elements/download_ab_elements.yaml") or {}
        self._elements.update(ab_elements)
        # 切量配置（切量名 / radio / 埋点表 提测后在 data yaml 回填）
        self._split_cfg = (load_yaml(_AB_DATA_PATH) or {}).get("split_control", {})

    # ══════════════════════════════════════════════════════════════════════════
    # 切量控制（全局配置：UPDATE user_group_common + 清 Redis）
    # ══════════════════════════════════════════════════════════════════════════

    def is_split_configured(self, group_label: str) -> bool:
        """切量名 + 指定组 radio 是否均已回填（非 TODO）。"""
        group_name = str(self._split_cfg.get("group_name", ""))
        radio = str((self._split_cfg.get("radio") or {}).get(group_label, ""))
        if not group_name or group_name.startswith("TODO"):
            return False
        if not radio or radio.startswith("TODO"):
            return False
        return True

    def set_split_group(self, group_label: str, mysql_db, redis_db) -> bool:
        """把全局切量打到指定组（实验组1/2、对照组1/2），并清 Redis 缓存。

        机制来自 utils/一键修改_任意切量分组.py：
            UPDATE user_group_common SET radio=<radio> WHERE group_name=<切量名>;
            redis DEL znzmo:group:all

        :param group_label: "实验组1" / "实验组2" / "对照组1" / "对照组2"
        :param mysql_db: mysql_db fixture（薄客户端）
        :param redis_db: redis_db fixture（薄客户端）
        :return: True 已应用；False 表示切量名/radio 未配置（提测后回填），调用方应 skip
        """
        if not self.is_split_configured(group_label):
            _logger.warning("切量未配置（group_label=%s），跳过切量设置", group_label)
            return False

        table = self._split_cfg.get("table", "user_group_common")
        group_name = self._split_cfg["group_name"]
        radio = self._split_cfg["radio"][group_label]
        redis_key = self._split_cfg.get("redis_key", "znzmo:group:all")

        with mysql_db.connection(commit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {table} SET radio=%s WHERE group_name=%s",
                    [radio, group_name],
                )
                _logger.info(
                    "切量已更新: %s.radio=%r where group_name=%r (影响 %s 行)",
                    table, radio, group_name, cur.rowcount,
                )
        self.clear_split_redis(redis_db)
        self.wait.wait_for_timeout(800)
        return True

    def clear_split_redis(self, redis_db) -> None:
        """清除切量 Redis 缓存键（默认 znzmo:group:all），使切量改动即时生效。"""
        redis_key = self._split_cfg.get("redis_key", "znzmo:group:all")
        try:
            with redis_db.client() as r:
                r.delete(redis_key)
            _logger.info("已清除切量 Redis 缓存键: %s", redis_key)
        except Exception as e:
            _logger.warning("清除切量 Redis 缓存失败: %s", e)

    def query_split_record(self, account_id: str, mysql_db) -> Optional[dict]:
        """查询切量埋点表中某账号的最新记录（表名/字段提测后回填）。

        :return: {日期, 用户ID, 切量分组} dict；表未配置返回 None；无记录返回 {}
        """
        rcfg = self._split_cfg.get("record_table", {})
        table = str(rcfg.get("name", ""))
        if not table or table.startswith("TODO"):
            _logger.warning("切量埋点表未配置，无法查询记录")
            return None

        f_date = rcfg["field_date"]
        f_user = rcfg["field_user"]
        f_group = rcfg["field_group"]
        with mysql_db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {f_date}, {f_user}, {f_group} FROM {table} "
                    f"WHERE {f_user}=%s ORDER BY {f_date} DESC LIMIT 1",
                    [account_id],
                )
                row = cur.fetchone()
        if not row:
            return {}
        return {"date": row[0], "user_id": row[1], "group": row[2]}

    def count_split_records_today(self, account_id: str, date_str: str, mysql_db) -> Optional[int]:
        """统计某账号某日切量记录条数（TRACK-005 去重校验；表未配置返回 None）。"""
        rcfg = self._split_cfg.get("record_table", {})
        table = str(rcfg.get("name", ""))
        if not table or table.startswith("TODO"):
            return None
        f_date = rcfg["field_date"]
        f_user = rcfg["field_user"]
        with mysql_db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {f_user}=%s AND DATE({f_date})=%s",
                    [account_id, date_str],
                )
                return int(cur.fetchone()[0])

    # ══════════════════════════════════════════════════════════════════════════
    # 详情页价格探测
    # ══════════════════════════════════════════════════════════════════════════

    def get_detail_take_price_text(self) -> str:
        """读取详情页"到手价"文本（弹窗打开前调用）。"""
        return self._safe_text("detail_take_price")

    def has_detail_coupon_price(self) -> bool:
        """详情页是否出现"券后价"字样（实验组期望 False）。"""
        return self.is_field_visible("detail_coupon_price", timeout=1500)

    # ══════════════════════════════════════════════════════════════════════════
    # 弹窗字段可见性（语义化封装）
    # ══════════════════════════════════════════════════════════════════════════

    def is_field_visible(self, yaml_key: str, timeout: int = 2000) -> bool:
        """通用：按 yaml key 判断元素是否可见（短超时，避免 TODO_SELECTOR 长等）。"""
        try:
            return self.get_locator(yaml_key).first.is_visible(timeout=timeout)
        except Exception as e:
            _logger.debug("is_field_visible(%s) 失败: %s", yaml_key, e)
            return False

    def is_vip_discount_visible(self) -> bool:
        """弹窗"VIP立减"行是否展示。"""
        return self.is_field_visible("vip_discount_row")

    def is_vip_pending_tag_visible(self) -> bool:
        """弹窗"待激活 -5知币"诱导标签是否展示。"""
        return self.is_field_visible("vip_pending_tag")

    def is_coupon_section_visible(self) -> bool:
        """弹窗"下载抵扣券"区是否展示（复用继承的 download_vocher_section）。"""
        return self.is_field_visible("download_vocher_section")

    def is_coupon_unused_row_visible(self) -> bool:
        """弹窗"不使用 >"残留行是否展示（实验组无券时应 False）。"""
        return self.is_field_visible("coupon_unused_row")

    def has_promo_bundle(self) -> bool:
        """弹窗是否出现省钱礼包/搭售区。"""
        return self.is_field_visible("promo_bundle")

    def has_bottom_cash(self) -> bool:
        """底部条是否出现"+X元"现金项（实验组应 False）。"""
        return self.is_field_visible("bottom_cash", timeout=1500)

    def is_activity_discount_visible(self) -> bool:
        """弹窗"活动立减"行是否展示。"""
        return self.is_field_visible("activity_discount_row")

    # ══════════════════════════════════════════════════════════════════════════
    # 文案 / 金额读取
    # ══════════════════════════════════════════════════════════════════════════

    def get_main_button_text(self) -> str:
        """读取底部主按钮文案（实验组应"立即下载"）。"""
        return self._safe_text("main_button") or self._safe_text("confirm_btn")

    def get_bottom_bar_text(self) -> str:
        """读取底部合计条文本。"""
        return self._safe_text("bottom_bar")

    def get_activity_discount_text(self) -> str:
        """读取"活动立减"金额文本。"""
        return self._safe_text("activity_discount_row")

    def get_material_info(self) -> dict:
        """读取弹窗顶部素材信息块各字段是否展示（EXP-025）。"""
        return {
            "block": self.is_field_visible("material_block"),
            "thumb": self.is_field_visible("material_thumb"),
            "title": self.is_field_visible("material_title"),
            "id": self.is_field_visible("material_id"),
            "tags": self.is_field_visible("material_tags"),
            "guarantee": self.is_field_visible("guarantee_badge"),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 对照组搭售交互
    # ══════════════════════════════════════════════════════════════════════════

    def click_confirm_button(self) -> None:
        """点击弹窗内「立即下载」确认按钮（触发实际支付/下载）。

        复用继承的 confirm_btn selector（nonvip_download_elements.yaml）。
        """
        try:
            self.get_locator("confirm_btn").first.click(timeout=5000)
            self.wait.wait_for_timeout(500)
        except Exception as e:
            _logger.warning("click_confirm_button 失败: %s", e)

    def select_promo_package(self, index: int = 0) -> bool:
        """勾选第 index 个搭售套餐（对照组 CTRL-005 用）。"""
        try:
            opts = self.get_locator("promo_package_option")
            opts.first.wait_for(state="visible", timeout=3000)
            opts.nth(index).click(force=True)
            self.wait.wait_for_timeout(1000)
            return True
        except Exception as e:
            _logger.warning("勾选搭售套餐[%d]失败: %s", index, e)
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # 内部工具
    # ══════════════════════════════════════════════════════════════════════════

    def _safe_text(self, yaml_key: str, timeout: int = 2500) -> str:
        """按 yaml key 取首个匹配元素文本，失败返回空字符串。"""
        try:
            return self.get_locator(yaml_key).first.inner_text(timeout=timeout).strip()
        except Exception as e:
            _logger.debug("_safe_text(%s) 失败: %s", yaml_key, e)
            return ""
