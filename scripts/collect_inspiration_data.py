"""
创作灵感流程数据采集脚本
用途：
  1. 走完用例的关键导航路径
  2. 采集所有动态列表数据 + 搜索页 keyword
  3. 将采集结果写入 tests/data/create_inspiration_flow_data.yaml

运行：
  python scripts/collect_inspiration_data.py [--headless]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# 项目根加入 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright, Page

from common.yaml_loader import load_yaml
from common.snapshot_compare import save_snapshot_to_yaml


# ── 配置 ─────────────────────────────────────────────────────────────────────
DATA_YAML = "tests/data/create_inspiration_flow_data.yaml"
LOGIN_YAML = "tests/data/login_data.yaml"
SKIP_TEXTS = {"去创作", "近30天预估收益"}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _get_texts(page: Page, selector: str, max_items: int = 0) -> list[str]:
    """从 CSS selector 读取所有卡片文本，将有效行用 ' | ' 拼接。"""
    items = page.locator(selector)
    total = items.count()
    count = total if max_items == 0 else min(total, max_items)
    results = []
    for i in range(count):
        try:
            raw = items.nth(i).inner_text(timeout=5000)
            lines = [
                ln.strip()
                for ln in raw.split("\n")
                if ln.strip() and ln.strip() not in SKIP_TEXTS
            ]
            results.append(" | ".join(lines) if lines else raw.strip())
        except Exception:
            pass
    return results


def _click_new_tab(page: Page, locator_or_selector, timeout: int = 15000) -> Page:
    """点击元素，等待新 tab 打开并返回新 page；失败则返回原 page。"""
    context = page.context
    if isinstance(locator_or_selector, str):
        loc = page.locator(locator_or_selector)
    else:
        loc = locator_or_selector

    try:
        with context.expect_page(timeout=timeout) as page_info:
            loc.first.click(force=True)
        new_page = page_info.value
        new_page.wait_for_load_state("domcontentloaded", timeout=20000)
        return new_page
    except Exception:
        # 同 tab 跳转：扫描 context pages
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        for p in context.pages:
            if not p.is_closed() and p is not page:
                return p
        return page


def _close_extra_tabs(anchor: Page) -> None:
    """关闭除 anchor 外的所有标签页。"""
    for p in list(anchor.context.pages):
        if p is not anchor and not p.is_closed():
            try:
                p.close()
            except Exception:
                pass


# ── 主流程 ────────────────────────────────────────────────────────────────────

def collect(headless: bool = False) -> None:
    login_data = load_yaml(LOGIN_YAML) or {}
    creds = (login_data.get("cases") or [{}])[0]
    username = creds.get("username", "")
    password = creds.get("password", "")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=300)
        context = browser.new_context()
        context.set_default_timeout(30000)
        page = context.new_page()

        # ── 登录 ──────────────────────────────────────────────────────────────
        print("[1/9] 登录...")
        from pages.methods.login_page import LoginPage
        login = LoginPage(page)
        login.goto_login_page()
        login.login_with(username, password)
        print(f"      登录后 URL: {page.url}")

        # ── 进入创作灵感页 ─────────────────────────────────────────────────────
        print("[2/9] 悬停上传 → 创作灵感...")
        from pages.methods.home_page import HomePage
        home = HomePage(page)
        home.goto_homepage()
        insp_page = home.goto_create_inspiration_from_nav_and_switch()
        print(f"      创作灵感页: {insp_page.url}")

        # ── 创作中心 ───────────────────────────────────────────────────────────
        print("[3/9] 点首页 → 创作中心，采集榜单...")
        from pages.methods.creative_center_page import CreativeCenterPage
        cc = CreativeCenterPage(insp_page)
        cc.click_home_to_creative_center()
        print(f"      创作中心: {cc.page.url}")

        rank_3d = cc.get_rank_3d_default_items_texts()
        rank_su = cc.get_rank_su_default_items_texts()
        print(f"      3D爆款榜: {len(rank_3d)} 条")
        for i, t in enumerate(rank_3d):
            print(f"        [3D-{i+1}] {t}")
        print(f"      SU爆款榜: {len(rank_su)} 条")
        for i, t in enumerate(rank_su):
            print(f"        [SU-{i+1}] {t}")

        # ── 点 SU 榜 item → 创作灵感页 ────────────────────────────────────────
        print("[4/9] 点 SU 榜 item[0] → 创作灵感页...")
        cc.click_su_rank_item(index=0)
        insp_page = cc.page
        print(f"      灵感页: {insp_page.url}")

        # ── SU 模型默认列表 ────────────────────────────────────────────────────
        print("[5/9] 采集 SU 模型默认列表...")
        from pages.methods.create_inspiration_page import CreateInspirationPage
        insp = CreateInspirationPage(insp_page)
        su_items = insp.get_su_model_items_texts()
        print(f"      SU模型: {len(su_items)} 条")
        for i, t in enumerate(su_items):
            print(f"        [SU-{i+1}] {t}")

        # ── 切换二级 tab → 采集列表 ───────────────────────────────────────────
        print("[6/9] 切二级 tab[1] → 采集...")
        insp.switch_any_secondary_tab(index=1)
        su_items_b = insp.get_su_model_items_texts()
        print(f"      SU二级Tab: {len(su_items_b)} 条")
        for i, t in enumerate(su_items_b):
            print(f"        [SU-b-{i+1}] {t}")

        # ── 点 item → 展开参考区 → 采集 search keyword ─────────────────────────
        print("[7/9] 点 item[0] → 展开参考区 → 点图片采集 keyword...")
        insp.click_su_item(index=0)
        insp_page.wait_for_timeout(1500)

        search_url = ""
        search_keyword = ""
        try:
            # 点击参考图获取跳转 URL
            orig = insp_page
            search_url = insp.click_reference_image_and_get_url()
            print(f"      搜索页 URL: {search_url}")
            # 从 URL 提取 keyword 参数（保留 URL-encoded 形式）
            parsed = urlparse(search_url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            if "keyword" in qs:
                raw_kw = qs["keyword"][0]
                from urllib.parse import quote
                search_keyword = f"keyword={quote(raw_kw, safe='')}"
                print(f"      keyword 参数: {search_keyword}")
            else:
                # 直接取 query 字符串中的片段
                import re
                m = re.search(r"keyword=[^&]+", parsed.query)
                if m:
                    search_keyword = m.group(0)
                    print(f"      keyword (raw): {search_keyword}")
        except Exception as e:
            print(f"      ⚠ 获取 keyword 失败: {e}")

        # ── 为你精选 tab ──────────────────────────────────────────────────────
        print("[8/9] 切换 为你精选 tab...")
        _close_extra_tabs(insp_page)
        insp.click_main_tab("为你精选")
        for_you_items = insp.get_current_tab_items_texts()
        print(f"      为你精选: {len(for_you_items)} 条")
        for i, t in enumerate(for_you_items):
            print(f"        [精选-{i+1}] {t}")

        # ── CAD图纸 tab ───────────────────────────────────────────────────────
        print("[9/9] 切换 CAD图纸 tab...")
        insp.click_main_tab("CAD图纸")
        cad_items = insp.get_current_tab_items_texts()
        print(f"      CAD图纸: {len(cad_items)} 条")
        for i, t in enumerate(cad_items):
            print(f"        [CAD-{i+1}] {t}")

        browser.close()

    # ── 写入 YAML ─────────────────────────────────────────────────────────────
    print("\n[写入] 更新 YAML 数据文件...")

    # 1. 更新静态 keyword 配置（若成功采集到）
    if search_keyword:
        yaml_path = ROOT / DATA_YAML
        text = yaml_path.read_text(encoding="utf-8")
        import re
        new_line = f'expected_search_keyword: "{search_keyword}"'
        if re.search(r"^expected_search_keyword:", text, re.MULTILINE):
            text = re.sub(r"^expected_search_keyword:.*$", new_line, text, flags=re.MULTILINE)
        else:
            text = new_line + "\n" + text
        yaml_path.write_text(text, encoding="utf-8")
        print(f"  expected_search_keyword → {search_keyword}")

    # 2. 写入快照列表数据
    snapshot_data = {
        "rank_3d": rank_3d,
        "rank_su": rank_su,
        "su_model_items": su_items,
        "su_model_items_secondary_tab": su_items_b,
        "for_you_items": for_you_items,
        "cad_items": cad_items,
    }
    save_snapshot_to_yaml(DATA_YAML, snapshot_data)
    print("\n[完成] 数据采集完成，YAML 已更新。")
    print("   接下来运行用例：pytest tests/cases/test_create_inspiration_flow.py -s -v")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创作灵感数据采集")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    args = parser.parse_args()
    collect(headless=args.headless)
