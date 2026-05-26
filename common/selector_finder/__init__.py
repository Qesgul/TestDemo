"""
selector_finder — 元素定位模块。

将自然语言测试用例转换为 Playwright locator，通过人工点选获取，输出 YAML 供 BasePage.get_locator() 直接使用。

快速使用：
    from common.selector_finder import run_pipeline
    run_pipeline(url="https://example.com", input_file="tests/data/my_cases.md",
                 output_file="pages/elements/my_elements.yaml")
"""

from common.selector_finder.pipeline import run_pipeline

__all__ = ["run_pipeline"]
