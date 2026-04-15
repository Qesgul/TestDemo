import json

import pytest

from common.yaml_loader import load_yaml
from pages.methods.create_inspiration_page import CreateInspirationPage
from pages.methods.creative_center_page import CreativeCenterPage
from pages.methods.home_page import HomePage
from pages.methods.login_page import LoginPage
from pages.methods.publish_work_page import PublishWorkPage



EXPECTED = load_yaml("tests/data/create_inspiration_flow_expected.yaml")

EXPECTED_SEARCH_URL = EXPECTED.get("expected_search_url")

class TestCreateInspirationFlow:
    @pytest.mark.smoke
    @pytest.mark.main
    @pytest.mark.ui
    def test_create_inspiration_flow(self, page, assertion):
        print(f"=== 冒烟用例: 创作灵感流程 ===")

        # 1. 登录
        login_page = LoginPage(page)
        login_page.goto_login_page()
        login_page.login_with(EXPECTED.get("username"), EXPECTED.get("password"))

        # 2. 悬停”创作上传” -> 点击”创作灵感”
        home_page = HomePage(page)
        # home_page.goto_homepage()
        page = home_page.goto_create_inspiration_from_nav_and_switch()

        # 3. 点击首页 -> 进入创作中心
        creative_center = CreativeCenterPage(page)
        creative_center.click_home_to_creative_center()

        # 3. 校验 3D爆款榜/SU爆款榜默认数据
        rank_3d_items = creative_center.get_rank_3d_default_items_texts()
        rank_su_items = creative_center.get_rank_su_default_items_texts()
        # 若 expected 已补齐，则进行严格校验
        assertion.assert_equal(json.dumps(rank_3d_items, ensure_ascii=False) , EXPECTED.get("expected_rank_3d_default_items"), message="3D爆款榜默认数据不一致")
        assertion.assert_equal(json.dumps(rank_su_items, ensure_ascii=False) , EXPECTED.get("expected_rank_su_default_items"), message="SU爆款榜默认数据不一致")

        # 4. 点击“去创作” -> 发布作品页
        creative_center.click_go_create_from_rank()
        publish_work = PublishWorkPage(page)
        assertion.assert_true(publish_work.is_on_publish_page(), message="未进入发布作品页（请调优定位器）")

        # 5. 返回创作中心
        publish_work.back_to_creative_center()

        # 5. 点 SU榜 item -> 创作灵感页
        creative_center.click_su_rank_item(index=0)
        create_inspiration = CreateInspirationPage(page)

        # 5. 校验 SU 模型默认选中 + 列表存在
        su_model_items = create_inspiration.get_su_model_items_texts()
        assertion.assert_equal(create_inspiration.get_active_tab(),"SU模型", message="默认TAB错误")
        assertion.assert_equal(json.dumps(su_model_items, ensure_ascii=False) , EXPECTED.get("expected_su_model_list_items"), message="SU模型默认数据不一致")

        # 6. 切换任意二级 tab -> 展示对应数据
        create_inspiration.switch_any_secondary_tab(index=1)
        su_model_items = create_inspiration.get_su_model_items_texts()
        assertion.assert_equal(json.dumps(su_model_items, ensure_ascii=False) , EXPECTED.get("expected_su_model_list_itemsb", "[]"), message="SU模型默认数据不一致2")

        # 7. 点击 item -> 展开参考模型/参考灵感区域
        create_inspiration.click_su_item(index=0)
        reference_images_count = create_inspiration.get_reference_images_count()
        assertion.assert_true(reference_images_count == 12, message=f"参考区域图片数量不足：{reference_images_count}（请调优定位器）")
        assertion.assert_true(
            create_inspiration.is_reference_more_button_visible(),
            message="参考区域“更多”按钮不可见（请调优定位器）",
        )

        # 8. 点击图片 -> 打开搜索页并校验关键词 -> 关闭新tab
        url_before_image = page.url
        search_url_1 = create_inspiration.click_reference_image_and_get_url()

        assertion.assert_equal(EXPECTED_SEARCH_URL , search_url_1, message="图片跳转搜索页关键词不匹配")

        # 9. 点击“更多”按钮 -> 再次打开搜索页并校验关键词
        url_before_more = page.url
        search_url_2 = create_inspiration.click_reference_more_button_and_get_url()
        assertion.assert_true(EXPECTED_SEARCH_URL , search_url_2, message="更多按钮跳转搜索页关键词不匹配")

        print("✅ 创作灵感冒烟流程执行完成")

