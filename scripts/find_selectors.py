#!/usr/bin/env python
"""
selector_finder CLI 入口。

用法：
    python scripts/find_selectors.py \\
        --url https://example.com/login \\
        --input tests/data/login_flow.md \\
        --output pages/elements/login_elements.yaml

可选参数：
    --report        完整报告 YAML 路径（含备选策略、元数据）
    --no-human      跳过人工兜底阶段（仅 yaml 复用）
    --browser       浏览器类型：chromium | firefox | webkit（默认 chromium）
    --elements-dir  现有元素 yaml 目录（默认 pages/elements）
"""

import argparse
import logging
import sys
from pathlib import Path

# 保证项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.selector_finder.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从测试用例中提取页面元素 selector，输出 Playwright YAML"
    )
    parser.add_argument("--url", required=True, help="目标页面 URL")
    parser.add_argument("--input", required=True, help="测试用例文件（Markdown/txt）")
    parser.add_argument("--output", required=True, help="输出的元素 YAML 路径")
    parser.add_argument("--report", default=None, help="完整报告 YAML 路径（可选）")
    parser.add_argument("--no-human", action="store_true", help="跳过人工兜底，仅走 yaml 复用")
    parser.add_argument(
        "--browser",
        default="chromium",
        choices=["chromium", "firefox", "webkit"],
        help="浏览器类型",
    )
    parser.add_argument(
        "--elements-dir",
        default="pages/elements",
        help="现有元素 yaml 目录（用于复用检查，默认 pages/elements）",
    )
    # 兼容旧参数
    parser.add_argument("--retries", type=int, default=3, help="保留参数（当前未使用）")
    args = parser.parse_args()

    report = run_pipeline(
        url=args.url,
        input_file=args.input,
        output_file=args.output,
        report_file=args.report,
        enable_human_picker=not args.no_human,
        browser_type=args.browser,
        elements_yaml_dir=args.elements_dir,
        max_retries=args.retries,
    )

    print("\n[完成]")
    print(f"  yaml 复用: {report.yaml_reuse_count} 个")
    print(f"  人工点选: {report.human_count} 个")
    print(f"  未解析:   {len(report.missing)} 个")
    print(f"  输出:     {args.output}")

    if report.missing:
        print("\n未解析元素（需人工补充）：")
        for s in report.missing:
            print(f"  [{s.step_index}] {s.element_desc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
