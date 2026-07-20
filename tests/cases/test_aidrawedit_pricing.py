# -*- coding: utf-8 -*-
"""AIDrawEdit 定价采集 - 全领域全场景遍历

流程（单次登录连续执行，每个领域独立）：
  1. 上传图片
  2. 切换到目标领域
  3. 获取全部场景（顶部可见 + 更多弹窗）
  4. 非编辑模式：遍历场景 → 逐模型采集价格+API
  5. 涂抹进入编辑模式
  6. 编辑模式：遍历场景（不可选跳过）→ 逐模型采集价格+API
  7. 汇总输出 + 保存 API 参数映射

运行：
  pytest tests/cases/test_aidrawedit_pricing.py -v
  DOMAIN=0 pytest tests/cases/test_aidrawedit_pricing.py -v  # 只跑通用设计
  DOMAIN=1 pytest tests/cases/test_aidrawedit_pricing.py -v  # 只跑室内设计
  DOMAIN=3 pytest tests/cases/test_aidrawedit_pricing.py -v  # 只跑建筑设计
  DOMAIN=4 pytest tests/cases/test_aidrawedit_pricing.py -v  # 只跑景观设计
"""
import json
import os
from pathlib import Path

import pytest

from common.pricing_helpers import api_login, inject_cookie, OUTPUT_DIR
from pages.methods.aidrawedit_pricing_page import AIDrawEditPricingPage, DOMAINS

pytestmark = pytest.mark.xdist_group("pricing")

_MEMBER = "新钻石会员"

# 支持通过 DOMAIN 环境变量指定单个领域（0=通用 1=室内 3=建筑 4=景观）
_domain_env = os.environ.get("DOMAIN")
_ALL_DOMAINS = [0, 1, 3, 4]
_DOMAINS_TO_TEST = [int(_domain_env)] if _domain_env is not None else _ALL_DOMAINS


@pytest.fixture(scope="class")
def pricing_session(browser):
    context = browser.new_context(no_viewport=True)
    page = context.new_page()
    token = api_login(_MEMBER)
    inject_cookie(page, token)
    yield page, token
    page.close()
    context.close()


def _run_domain(pp, domain, assertion):
    """单个领域的完整采集流程。

    流程：上传图片 → 通过 UI 选择器切换领域 → 采集。
    注意：上传图片会导致 URL 跳回默认领域（?domain=0），
    所以必须先上传，再通过页面左上角选择器切换领域（非 URL 导航）。
    """
    domain_name = DOMAINS[domain]

    # 先上传图片（上传后页面会跳回默认领域）
    pp.upload_image()
    # 再通过 UI 选择器切换到目标领域
    pp.switch_domain_via_selector(domain)

    # 获取全部场景
    scenes = pp.get_all_scenes()
    all_names = scenes["visible"] + scenes["more"]
    print(f"\n  {domain_name}: 顶部={scenes['visible']}, 更多={scenes['more']}")

    assertion.assert_true(
        len(all_names) >= 1,
        name=f"{domain_name}_scene_count",
        message=f"{domain_name} 至少有1个场景",
    )

    # ── 非编辑模式 ──
    results_non_edit = []
    for i, name in enumerate(all_names):
        print(f"\n  [{i+1}/{len(all_names)}] 非编辑-{name}...", end=" ", flush=True)
        try:
            if not pp.select_scene_safe(name):
                print("跳过(无法选中)")
                continue
            rs = pp.capture_scene_all_models(name, mode="非编辑")
            for r in rs:
                r["domain"] = domain_name
            results_non_edit.extend(rs)
            print(f"✓ {len(rs)} 条")
            for r in rs:
                print(f"    {r['model']:<20} {r['price_text']:<10} API={r.get('api_amount', '-')}")
        except Exception as e:
            print(f"错误: {e}")

    # ── 涂抹 ──
    pp.paint_on_canvas()

    # ── 编辑模式 ──
    results_edit = []
    for i, name in enumerate(all_names):
        print(f"\n  [{i+1}/{len(all_names)}] 编辑-{name}...", end=" ", flush=True)
        try:
            if not pp.select_scene_safe(name):
                print("跳过(无法选中)")
                continue
            rs = pp.capture_scene_all_models(name, mode="编辑")
            for r in rs:
                r["domain"] = domain_name
            results_edit.extend(rs)
            print(f"✓ {len(rs)} 条")
            for r in rs:
                print(f"    {r['model']:<20} {r['price_text']:<10} API={r.get('api_amount', '-')}")
        except Exception as e:
            print(f"错误: {e}")

    return results_non_edit, results_edit


class TestAllDomains:
    """全领域 × 全场景定价采集。"""

    @pytest.mark.core
    def test_all_domains(self, pricing_session, assertion):
        """上传 → 遍历领域 → 非编辑遍历 → 涂抹 → 编辑遍历。"""
        page, _ = pricing_session
        pp = AIDrawEditPricingPage(page, auto_close_popups=False)

        # API 拦截提前启用（route 不依赖当前 URL）
        pp.enable_api_intercept()
        # 首次导航到页面（后续每个领域由 _run_domain 负责）
        pp.goto()

        all_results_non_edit = []
        all_results_edit = []

        for domain in _DOMAINS_TO_TEST:
            domain_name = DOMAINS[domain]
            print(f"\n{'='*70}")
            print(f"  领域: {domain_name}")
            print(f"{'='*70}")

            ne, ed = _run_domain(pp, domain, assertion)
            all_results_non_edit.extend(ne)
            all_results_edit.extend(ed)
            print(f"\n  {domain_name} 完成: 非编辑={len(ne)}条, 编辑={len(ed)}条")

        # ── 汇总 ──
        lines = ["", "=" * 80, "  全领域定价采集汇总", "=" * 80]

        lines.append(f"\n  ── 非编辑模式 ({len(all_results_non_edit)} 条) ──")
        lines.append(f"  {'领域':<10} {'场景':<15} {'模型':<18} {'价格':<8} {'API':<8}")
        lines.append("  " + "-" * 60)
        for r in all_results_non_edit:
            lines.append(f"  {r.get('domain',''):<10} {r['scene']:<15} {r['model']:<18} {r['price_text']:<8} {r['api_amount'] or '-':<8}")

        lines.append(f"\n  ── 编辑模式 ({len(all_results_edit)} 条) ──")
        lines.append(f"  {'领域':<10} {'场景':<15} {'模型':<18} {'价格':<8} {'API':<8}")
        lines.append("  " + "-" * 60)
        for r in all_results_edit:
            lines.append(f"  {r.get('domain',''):<10} {r['scene']:<15} {r['model']:<18} {r['price_text']:<8} {r['api_amount'] or '-':<8}")

        lines.append(f"\n  API 拦截总数: {len(pp.api_captured)}")
        lines.append("=" * 80)
        print("\n".join(lines))

        # ── 保存 API 参数映射 ──
        api_map = {}
        for r in all_results_non_edit + all_results_edit:
            p = r.get("api_params")
            if p and isinstance(p, dict):
                key = f"{r['domain']}_{r['scene']}_{r['model']}"
                api_map[key] = {
                    "domain_name": r["domain"],
                    "scene": r["scene"],
                    "model": r["model"],
                    "mode": r["mode"],
                    "api_params": p,
                    "expected_amount": r.get("api_amount"),
                }
        out_path = OUTPUT_DIR / "aidrawedit_api_params.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(api_map, f, ensure_ascii=False, indent=2)
        print(f"\n  API 参数已保存: {out_path}")
