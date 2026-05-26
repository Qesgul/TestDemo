"""
创作灵感流程 - 冒烟用例

URL 入口: https://www.znzmo.com/?from=personalCenter
  -> 悬停"上传" -> 点击"创作灵感"

覆盖：
- TC-CI-001：完整创作灵感主流程
    1. 导航首页（已登录态，跳过重复登录）
    2. 悬停"上传" -> 点击"创作灵感"
    3. 点击首页 -> 进入创作中心，采集 3D爆款榜 / SU爆款榜数据并与快照比对
    4. 点击"去创作" -> 进入发布作品页校验（URL 包含 creatorCenter/upload）
    5. 返回创作中心 -> 点 SU榜 item -> 创作灵感页，校验 SU 模型默认 Tab + 列表非空
    6. 切换任意二级 tab -> 列表刷新且非空
    7. 点击 item -> 展开参考模型/参考灵感区域，校验图片可见 + 更多按钮可见
    8. 点击图片 -> 新 tab 打开搜索页并校验 URL 包含预期 keyword
    9. 点击"更多"按钮 -> 再次打开搜索页并校验 URL 包含预期 keyword
   10. 切换"为你精选" Tab -> 校验激活态 + 数据采集与快照比对
   11. 切换"CAD图纸" Tab -> 校验激活态 + 数据采集与快照比对
   12. CAD Tab 下点击"去创作" -> 校验上传页 URL 含 classifyType=3 + CAD图纸 radio 预选

性能：
- 使用 conftest.py 的 logged_in_page fixture（session 级 storage_state 复用），
  整个会话仅登录一次，后续 test 直接拿到已登录态 page，无需在用例体内重复执行登录。

断言策略：
- 排行榜 / 模型列表等动态数据：
    * 将卡片完整信息（序号 | 名称 | 下载量 | 收益区间）写入数据文件的 snapshots 键
    * 与上次运行结果做差量比对（新增/减少/不变），输出可读报告
    * 存在性断言由 assert_not_empty() 统一处理，结合快照上下文给出明确错误信息
    * 质量断言：all(text.strip() for text in items) 确保无空字符串条目
- 搜索 URL keyword：校验 URL 中包含预期的关键词参数，轻量且稳定。

快照存储：tests/data/create_inspiration_flow_data.yaml → snapshots 键
- 首次运行：写入当前数据作为基准（无比对，无断言差异）
- 后续运行：先比对、后用新数据覆盖快照，保持快照与最新运行同步
- 文件中原有注释和静态配置（expected_search_keyword 等）原样保留

注意 - 标签页切换处理：
- "去创作"、"SU榜 item 点击"等操作均可能打开新标签页，
  Page Object 的对应方法会自动 switch_to_new_tab；
  操作完成后需通过 <page_object>.page 更新测试的 page 变量。
"""

import pytest

from common.snapshot_compare import (
    assert_not_empty,
    compare_and_print,
    load_snapshot_from_yaml,
    save_snapshot_to_yaml,
)
from common.yaml_loader import load_yaml
from pages.methods.create_inspiration_page import CreateInspirationPage
from pages.methods.creative_center_page import CreativeCenterPage
from pages.methods.home_page import HomePage
from pages.methods.publish_work_page import PublishWorkPage


_DATA_PATH = "tests/data/create_inspiration_flow_data.yaml"
_DATA = load_yaml(_DATA_PATH)

# 搜索页 URL 中必须包含的 keyword 参数（比完整 URL 比较更宽松）
_EXPECTED_SEARCH_KEYWORD = _DATA.get("expected_search_keyword", "")
# 保留完整 URL 以支持精确比较（如需要时在 YAML 中配置）
_EXPECTED_SEARCH_URL = _DATA.get("expected_search_url", "")


class TestCreateInspirationFlow:

    @pytest.mark.smoke
    @pytest.mark.main
    @pytest.mark.ui
    def test_create_inspiration_flow(self, logged_in_page, assertion):
        """TC-CI-001（P0）：创作灵感完整主流程冒烟用例。"""
        print("=== TC-CI-001: 创作灵感冒烟流程 ===")

        page = logged_in_page  # 已登录态，无需再执行登录步骤

        # 从数据文件的 snapshots 键读取上次快照（首次运行时为空字典）
        prev_data: dict = load_snapshot_from_yaml(_DATA_PATH)
        current_data: dict = {}  # 本次采集数据，测试末尾统一写入快照

        # -- 步骤 1：导航到首页 -------------------------------------------------
        home_page = HomePage(page)
        home_page.goto_homepage()

        # -- 步骤 2：悬停"上传" -> 点击"创作灵感" --------------------------------
        # 可能打开新 tab；switch 后 home_page.page 更新为新 tab 的 Page
        page = home_page.goto_create_inspiration_from_nav_and_switch()
        print(f"    [步骤2] 创作灵感页 URL: {page.url}")

        # -- 步骤 3：点击首页 -> 进入创作中心 ------------------------------------
        creative_center = CreativeCenterPage(page)
        creative_center.click_home_to_creative_center()
        print(f"    [步骤3] 创作中心 URL: {page.url}")

        # -- 步骤 3：采集 3D爆款榜 / SU爆款榜 + 快照比对 -----------------------
        rank_3d_items = creative_center.get_rank_3d_default_items_texts()
        rank_su_items = creative_center.get_rank_su_default_items_texts()

        print(f"    3D爆款榜全量数据（共 {len(rank_3d_items)} 条）:")
        for i, t in enumerate(rank_3d_items):
            print(f"      [3D-{i + 1}] {t}")
        compare_and_print("rank_3d", prev_data.get("rank_3d", []), rank_3d_items)

        print(f"    SU爆款榜全量数据（共 {len(rank_su_items)} 条）:")
        for i, t in enumerate(rank_su_items):
            print(f"      [SU-{i + 1}] {t}")
        compare_and_print("rank_su", prev_data.get("rank_su", []), rank_su_items)

        current_data["rank_3d"] = rank_3d_items
        current_data["rank_su"] = rank_su_items

        assert_not_empty("3D爆款榜", rank_3d_items, prev_data.get("rank_3d", []), assertion)
        assert_not_empty("SU爆款榜", rank_su_items, prev_data.get("rank_su", []), assertion)
        assertion.assert_true(
            all(text.strip() for text in rank_3d_items),
            message=f"3D爆款榜存在空文本条目，选择器可能命中了容器而非文本: {rank_3d_items}",
        )
        assertion.assert_true(
            all(text.strip() for text in rank_su_items),
            message=f"SU爆款榜存在空文本条目，选择器可能命中了容器而非文本: {rank_su_items}",
        )

        # -- 步骤 4：点击"去创作" -> 发布作品页 -----------------------------------
        # click_go_create_from_rank 会自动处理新标签页，通过 creative_center.page 取最新引用
        creative_center.click_go_create_from_rank()
        page = creative_center.page  # 可能已切换到发布作品页新 tab
        publish_work = PublishWorkPage(page)
        print(f"    [步骤4] 发布作品页 URL: {publish_work.get_current_url()}")
        assertion.assert_true(
            publish_work.is_on_publish_page(),
            message=f"未进入发布作品页（URL 不含 creatorCenter/upload，实际: {publish_work.get_current_url()}，请调优定位器）",
        )

        # -- 步骤 5a：返回创作中心 -----------------------------------------------
        # back_to_creative_center 会关闭新 tab 或执行后退，通过 publish_work.page 取最新引用
        publish_work.back_to_creative_center()
        page = publish_work.page  # 切回创作中心 tab
        print(f"    [步骤5a] 返回后 URL: {page.url}")

        # -- 步骤 5b：点 SU榜 item -> 创作灵感页 ----------------------------------
        # 重新绑定 creative_center 到当前 page（back 后 page 已更新）
        creative_center = CreativeCenterPage(page)
        creative_center.click_su_rank_item(index=0)
        page = creative_center.page  # 可能已切换到创作灵感新 tab
        print(f"    [步骤5b] 创作灵感页 URL: {page.url}")

        # -- 步骤 5c：校验 SU 模型默认 Tab + 列表数据采集与比对 -------------------
        create_inspiration = CreateInspirationPage(page)
        active_tab = create_inspiration.get_active_tab()
        su_model_items = create_inspiration.get_su_model_items_texts()

        print(f"    创作灵感页激活 Tab: {active_tab!r}")
        print(f"    SU模型全量数据（共 {len(su_model_items)} 条）:")
        for i, t in enumerate(su_model_items):
            print(f"      [SU-{i + 1}] {t}")
        compare_and_print("su_model_items", prev_data.get("su_model_items", []), su_model_items)

        current_data["su_model_items"] = su_model_items

        assertion.assert_equal(
            active_tab,
            "SU模型",
            message=f"默认激活 Tab 错误，期望「SU模型」，实际「{active_tab}」",
        )
        assert_not_empty("SU模型列表", su_model_items, prev_data.get("su_model_items", []), assertion)
        assertion.assert_true(
            all(text.strip() for text in su_model_items),
            message=f"SU模型列表存在空文本条目，数据异常: {su_model_items}",
        )

        # -- 步骤 6：切换任意二级 tab -> 数据刷新比对 -----------------------------
        create_inspiration.switch_any_secondary_tab(index=1)
        su_model_items_b = create_inspiration.get_su_model_items_texts()

        print(f"    SU二级 Tab 切换后全量数据（共 {len(su_model_items_b)} 条）:")
        for i, t in enumerate(su_model_items_b):
            print(f"      [SU-b-{i + 1}] {t}")
        compare_and_print("su_model_items_secondary_tab", prev_data.get("su_model_items_secondary_tab", []), su_model_items_b)

        current_data["su_model_items_secondary_tab"] = su_model_items_b

        assert_not_empty("SU模型二级 Tab 列表", su_model_items_b, prev_data.get("su_model_items_secondary_tab", []), assertion)
        assertion.assert_true(
            all(text.strip() for text in su_model_items_b),
            message=f"切换二级 tab 后存在空文本条目，数据异常: {su_model_items_b}",
        )

        # -- 步骤 7：点击 item -> 展开参考模型/参考灵感区域 -----------------------
        create_inspiration.click_su_item(index=0)
        reference_images_count = create_inspiration.get_reference_images_count()
        more_btn_visible = create_inspiration.is_reference_more_button_visible()
        print(f"    参考区域图片数: {reference_images_count}, 更多按钮可见: {more_btn_visible}")
        assertion.assert_true(
            reference_images_count >= 1,
            message=f"参考区域无图片（实际数量 {reference_images_count}，请调优选择器 reference_images）",
        )
        assertion.assert_true(
            more_btn_visible,
            message="参考区域「更多」按钮不可见（请调优选择器 reference_more_button）",
        )

        # -- 步骤 8：点击图片 -> 新 tab 搜索页，校验 URL 含预期 keyword ----------
        search_url_1 = create_inspiration.click_reference_image_and_get_url()
        print(f"    [步骤8] 搜索页 URL: {search_url_1}")
        if _EXPECTED_SEARCH_KEYWORD:
            assertion.assert_true(
                _EXPECTED_SEARCH_KEYWORD in search_url_1,
                message=f"图片跳转搜索页 keyword 不匹配，期望包含 {_EXPECTED_SEARCH_KEYWORD!r}，实际 URL: {search_url_1}",
            )
        elif _EXPECTED_SEARCH_URL:
            assertion.assert_equal(
                search_url_1,
                _EXPECTED_SEARCH_URL,
                message=f"图片跳转搜索页 URL 不匹配，实际 URL: {search_url_1}",
            )
        else:
            assertion.assert_true(
                bool(search_url_1) and "znzmo.com" in search_url_1,
                message=f"图片跳转的 URL 异常: {search_url_1!r}",
            )

        # -- 步骤 9：点击"更多"按钮 -> 再次打开搜索页，校验关键词 ----------------
        search_url_2 = create_inspiration.click_reference_more_button_and_get_url()
        print(f"    [步骤9] 搜索页 URL: {search_url_2}")
        if _EXPECTED_SEARCH_KEYWORD:
            assertion.assert_true(
                _EXPECTED_SEARCH_KEYWORD in search_url_2,
                message=f"「更多」跳转搜索页 keyword 不匹配，期望包含 {_EXPECTED_SEARCH_KEYWORD!r}，实际 URL: {search_url_2}",
            )
        elif _EXPECTED_SEARCH_URL:
            assertion.assert_equal(
                search_url_2,
                _EXPECTED_SEARCH_URL,
                message=f"「更多」跳转搜索页 URL 不匹配，实际 URL: {search_url_2}",
            )
        else:
            assertion.assert_true(
                bool(search_url_2) and "znzmo.com" in search_url_2,
                message=f"「更多」按钮跳转的 URL 异常: {search_url_2!r}",
            )

        # -- 步骤 10：切换"为你精选" Tab -> 校验激活态 + 数据采集与比对 ----------
        create_inspiration.click_main_tab("为你精选")
        active_tab_10 = create_inspiration.get_active_tab()
        for_you_items = create_inspiration.get_current_tab_items_texts()

        print(f"    [步骤10] 为你精选 Tab 激活态: {active_tab_10!r}")
        print(f"    为你精选全量数据（共 {len(for_you_items)} 条）:")
        for i, t in enumerate(for_you_items):
            print(f"      [精选-{i + 1}] {t}")
        compare_and_print("for_you_items", prev_data.get("for_you_items", []), for_you_items)

        current_data["for_you_items"] = for_you_items

        assertion.assert_equal(
            active_tab_10,
            "为你精选",
            message=f"切换 Tab 后激活项错误，期望「为你精选」，实际「{active_tab_10}」",
        )
        assert_not_empty("为你精选 Tab 列表", for_you_items, prev_data.get("for_you_items", []), assertion)
        assertion.assert_true(
            all(text.strip() for text in for_you_items),
            message=f"「为你精选」Tab 存在空文本条目，数据异常: {for_you_items}",
        )

        # -- 步骤 11：切换"CAD图纸" Tab -> 校验激活态 + 数据采集与比对 ----------
        create_inspiration.click_main_tab("CAD图纸")
        active_tab_11 = create_inspiration.get_active_tab()
        cad_items = create_inspiration.get_current_tab_items_texts()

        print(f"    [步骤11] CAD图纸 Tab 激活态: {active_tab_11!r}")
        print(f"    CAD图纸全量数据（共 {len(cad_items)} 条）:")
        for i, t in enumerate(cad_items):
            print(f"      [CAD-{i + 1}] {t}")
        compare_and_print("cad_items", prev_data.get("cad_items", []), cad_items)

        current_data["cad_items"] = cad_items

        assertion.assert_equal(
            active_tab_11,
            "CAD图纸",
            message=f"切换 Tab 后激活项错误，期望「CAD图纸」，实际「{active_tab_11}」",
        )
        assert_not_empty("CAD图纸 Tab 列表", cad_items, prev_data.get("cad_items", []), assertion)
        assertion.assert_true(
            all(text.strip() for text in cad_items),
            message=f"「CAD图纸」Tab 存在空文本条目，数据异常: {cad_items}",
        )

        # -- 步骤 12：CAD Tab 下点击「去创作」-> 校验上传页 URL + CAD图纸预选 ----
        original_inspiration_page = create_inspiration.page
        upload_page_obj = create_inspiration.click_cad_go_create_and_switch()
        cad_upload_url = upload_page_obj.url
        print(f"    [步骤12] 上传页 URL: {cad_upload_url}")

        # 用 PublishWorkPage 的方法校验（不在 test 层直接写 selector）
        upload_work = PublishWorkPage(upload_page_obj)
        cad_url_ok = "classifyType=3" in cad_upload_url
        cad_selected = upload_work.is_cad_category_selected()
        print(f"    URL 含 classifyType=3: {cad_url_ok}, CAD图纸 radio checked: {cad_selected}")

        assertion.assert_true(
            cad_url_ok,
            message=f"「去创作」未跳转至 CAD 品类上传页，URL 应含 classifyType=3，实际: {cad_upload_url}",
        )
        assertion.assert_true(
            cad_selected,
            message="上传页品类「CAD图纸」未被预选（radio not checked）",
        )

        # 关闭上传新 tab，回到创作灵感页
        create_inspiration.close_current_and_switch_to_original(original_inspiration_page)

        # -- 保存本次快照到数据文件（覆盖 snapshots 键，供下次运行比对）----------
        save_snapshot_to_yaml(_DATA_PATH, current_data)

        print("=== TC-CI-001 创作灵感冒烟流程执行完成 ===")
