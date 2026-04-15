#!/usr/bin/env python
"""
知末网自动化测试执行器 (YAML 配置)
只支持分组执行和标签执行两种方式
"""
import argparse
import subprocess
import sys
import os
from typing import List, Dict, Any

from common.yaml_loader import load_yaml
from config.settings import get_config


class TestRunner:
    """测试执行器"""

    def __init__(self, config_path: str = "test_suite.yaml"):
        """
        初始化测试执行器
        :param config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.base_command = [sys.executable, "-m", "pytest", "-v"]

        # 从 config/settings.py 读取执行配置（统一配置管理）
        self._config = get_config()

        # 并发执行配置
        self.parallel_enabled = self._config.execution.parallel_enabled
        self.parallel_workers = self._config.execution.parallel_workers
        self.parallel_dist_mode = self._config.execution.parallel_dist_mode

        # 失败重试配置
        self.retry_enabled = self._config.execution.retry_enabled
        self.retry_max_reruns = self._config.execution.retry_max_reruns
        self.retry_delay = self._config.execution.retry_delay
        self.retry_only_flaky = self._config.execution.retry_only_flaky

        # Allure 报告配置
        self.allure_config = {
            "enabled": self._config.allure.enabled,
            "results_dir": self._config.allure.results_dir,
            "report_dir": self._config.allure.report_dir,
            "clean_results": self._config.allure.clean_results,
            "open_report": self._config.allure.open_report,
            "report_title": self._config.allure.report_title
        }

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            print(f"错误: 配置文件 {self.config_path} 不存在")
            sys.exit(1)
        return load_yaml(self.config_path) or self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "groups": [],
            "available_tags": []
        }

    def list_groups(self) -> None:
        """列出所有配置的测试分组"""
        print("=" * 70)
        print("可用的测试分组:")
        print("=" * 70)

        groups = self.config.get("groups", [])
        if not groups:
            print("  没有配置任何分组")
            return

        for idx, group in enumerate(groups, 1):
            print(f"\n[{idx}] {group.get('name', '未命名分组')}")
            print(f"    描述: {group.get('description', '无描述')}")
            print(f"    标签: {group.get('tags', [])}")
            print(f"    包含用例:")
            cases = group.get("cases", [])
            for case in cases:
                if isinstance(case, dict):
                    case_file = case.get("file", "")
                    case_name = case.get("case", "")
                    if case_name:
                        print(f"      - {os.path.basename(case_file)}:{case_name}")
                    else:
                        print(f"      - {os.path.basename(case_file)}")
                else:
                    print(f"      - {os.path.basename(str(case))}")

        print("\n" + "=" * 70)

    def list_tags(self) -> None:
        """列出所有可用的标签"""
        print("=" * 70)
        print("可用的测试标签:")
        print("=" * 70)

        tags = self.config.get("available_tags", [])
        if not tags:
            print("  没有配置任何标签")
            return

        for tag in tags:
            print(f"  {tag['name']:10} - {tag['description']}")

        print("\n" + "=" * 70)

    def build_group_command(
        self,
        group_name: str,
        parallel: bool = None,
        workers: int = None,
        reruns: int = None,
    ) -> List[str]:
        """构建分组执行命令"""
        command = self.base_command.copy()

        # 处理并发执行参数
        parallel_enabled = parallel if parallel is not None else self.parallel_enabled
        if parallel_enabled:
            workers_count = workers if workers is not None else self.parallel_workers
            # 只使用 -n 参数，分发模式在 test_suite.yaml 中说明，使用 pytest-xdist 的默认行为
            # 对于 Playwright 测试，默认的分发模式已经足够好
            command.extend([
                "-n", str(workers_count)
            ])

        # 处理失败重试参数 - 使用自定义异常类型定向重试机制
        if self.retry_enabled:
            retry_reruns = reruns if reruns is not None else self.retry_max_reruns
            command.extend([
                "--max-reruns", str(retry_reruns)
            ])

        # 添加 Allure 报告配置
        if self.allure_config.get("enabled", True):
            command.extend([
                "--alluredir", self.allure_config.get("results_dir", "allure-results")
            ])
            if self.allure_config.get("clean_results", True):
                command.append("--clean-alluredir")

        command.append("-s")

        groups = self.config.get("groups", [])
        found_group = None
        for group in groups:
            if group.get("name") == group_name:
                found_group = group
                break

        if not found_group:
            print(f"错误: 未找到分组 '{group_name}'")
            return []

        cases = found_group.get("cases", [])
        test_paths = []

        for case in cases:
            if isinstance(case, dict):
                file_path = case.get("file", "")
                case_name = case.get("case", "")
                if file_path:
                    if case_name:
                        test_paths.append(f"{file_path}::{case_name}")
                    else:
                        test_paths.append(file_path)
            elif isinstance(case, str):
                test_paths.append(case)

        if not test_paths:
            print(f"警告: 分组 '{group_name}' 没有配置任何测试用例")
            return []

        command.extend(test_paths)
        return command

    def build_tags_command(
        self,
        tags: List[str],
        parallel: bool = None,
        workers: int = None,
        reruns: int = None,
    ) -> List[str]:
        """构建标签执行命令"""
        command = self.base_command.copy()

        # 处理并发执行参数
        parallel_enabled = parallel if parallel is not None else self.parallel_enabled
        if parallel_enabled:
            workers_count = workers if workers is not None else self.parallel_workers
            # 只使用 -n 参数，分发模式在 test_suite.yaml 中说明，使用 pytest-xdist 的默认行为
            # 对于 Playwright 测试，默认的分发模式已经足够好
            command.extend([
                "-n", str(workers_count)
            ])

        # 处理失败重试参数 - 使用自定义异常类型定向重试机制
        if self.retry_enabled:
            retry_reruns = reruns if reruns is not None else self.retry_max_reruns
            command.extend([
                "--max-reruns", str(retry_reruns)
            ])

        # 添加 Allure 报告配置
        if self.allure_config.get("enabled", True):
            command.extend([
                "--alluredir", self.allure_config.get("results_dir", "allure-results")
            ])
            if self.allure_config.get("clean_results", True):
                command.append("--clean-alluredir")

        command.append("-s")
        command.extend(["-m", " or ".join(tags)])
        command.append("tests/cases/")

        return command

    def run_command(self, command: List[str]) -> int:
        """运行命令"""
        # 清理空字符串
        command = [c for c in command if c]

        print(f"执行命令: {' '.join(command)}\n")

        try:
            process = subprocess.run(command)
            return process.returncode
        except Exception as e:
            print(f"执行失败: {e}")
            return 1

    def run_group(
        self,
        group_name: str,
        parallel: bool = None,
        workers: int = None,
        reruns: int = None,
    ) -> int:
        """运行指定分组"""
        print(f"运行分组: {group_name}")
        if parallel or (parallel is None and self.parallel_enabled):
            workers_count = workers if workers is not None else self.parallel_workers
            print(
                f"并发执行: 启用，进程数={workers_count}，分发模式={self.parallel_dist_mode}"
            )
        if reruns is not None or self.retry_enabled:
            retry_count = reruns if reruns is not None else self.retry_max_reruns
            # 当前 retry 延迟不进入 pytest 参数，仅用于提示
            print(f"失败重试: 启用，最大重试次数={retry_count}，重试延迟={self.retry_delay}秒")
        command = self.build_group_command(group_name, parallel, workers, reruns)
        if not command:
            return 1
        return self.run_command(command)

    def run_tags(
        self,
        tags: List[str],
        parallel: bool = None,
        workers: int = None,
        reruns: int = None,
    ) -> int:
        """运行指定标签的用例"""
        if not tags:
            print("错误: 没有指定标签")
            return 1
        print(f"运行标签: {', '.join(tags)}")
        if parallel or (parallel is None and self.parallel_enabled):
            workers_count = workers if workers is not None else self.parallel_workers
            print(
                f"并发执行: 启用，进程数={workers_count}，分发模式={self.parallel_dist_mode}"
            )
        if reruns is not None or self.retry_enabled:
            retry_count = reruns if reruns is not None else self.retry_max_reruns
            # 当前 retry 延迟不进入 pytest 参数，仅用于提示
            print(f"失败重试: 启用，最大重试次数={retry_count}，重试延迟={self.retry_delay}秒")
        command = self.build_tags_command(tags, parallel, workers, reruns)
        if not command:
            return 1
        return self.run_command(command)

    def generate_allure_report(self) -> None:
        """生成 Allure 报告"""
        # Allure 相关配置以 config/settings.py 的解析结果为准
        if not self.allure_config.get("enabled", True):
            return

        results_dir = self.allure_config.get("results_dir", "allure-results")
        report_dir = self.allure_config.get("report_dir", "allure-report")
        report_title = self.allure_config.get("report_title", "自动化测试报告")
        open_report = self.allure_config.get("open_report", True)

        if not os.path.exists(results_dir) or len(os.listdir(results_dir)) == 0:
            print("⚠️  Allure 结果目录为空，跳过报告生成")
            return

        print("\n" + "=" * 70)
        print("生成 Allure 报告...")
        print("=" * 70)

        try:
            # 检查 allure 命令是否可用
            allure_cmd = ["allure"]
            found_allure = False

            # 先尝试直接使用 allure 命令
            try:
                result = subprocess.run(
                    allure_cmd + ["--version"],
                    capture_output=True,
                    check=True,
                    text=True
                )
                print(f"✅ Allure 已检测到: {result.stdout.strip()}")
                found_allure = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                # 直接命令失败，尝试常见的安装路径
                common_paths = []

                # Windows 常见路径
                if sys.platform == "win32":
                    # Scoop 安装路径
                    home_dir = os.path.expanduser("~")
                    scoop_path = os.path.join(home_dir, "scoop", "shims", "allure.exe")
                    if os.path.exists(scoop_path):
                        common_paths.append(scoop_path)

                    # npm 全局安装路径
                    npm_path = os.path.join(
                        os.environ.get("APPDATA", ""),
                        "npm", "allure.cmd"
                    )
                    if os.path.exists(npm_path):
                        common_paths.append(npm_path)

                    # Chocolatey 安装路径
                    choco_path = os.path.join(
                        os.environ.get("ProgramData", ""),
                        "chocolatey", "bin", "allure.exe"
                    )
                    if os.path.exists(choco_path):
                        common_paths.append(choco_path)

                # Linux/macOS 常见路径
                else:
                    # npm 全局安装
                    for npm_dir in [
                        "/usr/local/bin/allure",
                        os.path.expanduser("~/.npm-global/bin/allure"),
                        os.path.expanduser("~/npm/bin/allure")
                    ]:
                        if os.path.exists(npm_dir) and os.access(npm_dir, os.X_OK):
                            common_paths.append(npm_dir)

                # 尝试找到的路径
                for path in common_paths:
                    try:
                        result = subprocess.run(
                            [path, "--version"],
                            capture_output=True,
                            check=True,
                            text=True
                        )
                        allure_cmd = [path]
                        print(f"✅ Allure 已检测到: {result.stdout.strip()} (路径: {path})")
                        found_allure = True
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue

            if not found_allure:
                print("\n⚠️  未找到 allure 命令")
                print("=" * 70)
                print("Allure 报告生成功能需要安装 Allure Commandline 工具。")
                print("\n请选择以下方式之一安装：")
                print("\n1. Windows (推荐使用 Scoop 包管理器):")
                print("   1) 安装 Scoop: https://scoop.sh/")
                print("   2) 执行命令: scoop install allure")

                print("\n2. 使用 npm (Node.js 包管理器):")
                print("   1) 确保已安装 Node.js: https://nodejs.org/")
                print("   2) 执行命令: npm install -g allure-commandline")

                print("\n3. 手动下载 (适用于所有系统):")
                print("   访问: https://docs.qameta.io/allure/#_installing_a_commandline")
                print("   下载适合你系统的版本，解压缩后将 bin 目录添加到系统 PATH 中")

                print("\n4. 临时解决方案: 使用 Python 内置服务器查看原始数据")
                print("   报告原始数据已保存在 allure-results/ 目录中。")
                print("   你可以使用以下命令启动一个简单的 HTTP 服务器查看结果：")
                print(f"   python -m http.server 8080 --directory {os.path.abspath(report_dir)}")
                print("\n5. 跳过报告生成:")
                print("   使用 --no-allure 参数禁用报告生成")

                # 提供快速启动 HTTP 服务器的选项
                user_input = input("\n是否要立即启动一个简单的 HTTP 服务器查看报告结果? (y/N): ").lower()
                if user_input == "y":
                    # 尝试启动 HTTP 服务器
                    print("\n📡 启动临时 HTTP 服务器查看报告结果...")
                    print(f"🚀 访问地址: http://localhost:8080")
                    print(f"📍 服务器根目录: {os.path.abspath(results_dir)}")
                    print(f"⚡ 按 Ctrl+C 停止服务器")

                    # 因为没有 Allure 报告，我们直接查看原始结果
                    original_dir = os.getcwd()
                    try:
                        import http.server
                        import socketserver

                        # 确保目录存在
                        os.makedirs(results_dir, exist_ok=True)

                        # 切换到结果目录启动服务器
                        os.chdir(results_dir)

                        with socketserver.TCPServer(("", 8080),
                                                   http.server.SimpleHTTPRequestHandler) as httpd:
                            print("\n✅ 服务器已启动")
                            print("=" * 70)
                            httpd.serve_forever()
                    except KeyboardInterrupt:
                        print("\n\n⏹️  服务器已停止")
                    except Exception as e:
                        print(f"❌ 启动服务器失败: {e}")
                        print(f"💡 手动启动命令: python -m http.server 8080 --directory \"{os.path.abspath(results_dir)}\"")
                    finally:
                        # 恢复原始工作目录
                        os.chdir(original_dir)
                else:
                    print("📥 结果已保存到 allure-results 目录")

                return

            # 清理旧报告
            if os.path.exists(report_dir):
                import shutil
                shutil.rmtree(report_dir)

            generate_cmd = allure_cmd + [
                "generate",
                results_dir,
                "-o", report_dir,
                "--title", report_title
            ]

            if open_report:
                print("正在生成并打开报告...")
                generate_cmd.extend(["--clean"])
                process = subprocess.run(generate_cmd)
                if process.returncode == 0:
                    subprocess.run(["allure", "open", report_dir])
            else:
                print("正在生成报告...")
                generate_cmd.extend(["--clean"])
                subprocess.run(generate_cmd)

            print(f"\n✅ Allure 报告已生成: {report_dir}")
            print("=" * 70)

        except Exception as e:
            print(f"\n⚠️  生成 Allure 报告时出错: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="知末网自动化测试执行器 (YAML 配置)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有分组和标签
  python run_suite.py --list-groups
  python run_suite.py --list-tags

  # 运行分组
  python run_suite.py --group "快速检查"
  python run_suite.py --group "核心功能"

  # 运行标签
  python run_suite.py --tags quick
  python run_suite.py --tags quick smoke
  python run_suite.py --tags core ui

  # 运行默认配置
  python run_suite.py

  # 禁用报告生成
  python run_suite.py --group "快速检查" --no-allure

  # 并发执行（配置文件中已启用）
  python run_suite.py --group "弹框专项"

  # 强制启用并发并指定进程数
  python run_suite.py --group "核心功能" --parallel --workers 4

  # 禁用并发执行（单进程运行）
  python run_suite.py --group "快速检查" --no-parallel

  # 自定义并发分发模式
  python run_suite.py --tags popup ui --dist-mode class

  # 配置参数
  python run_suite.py --group "快速检查" --env test --base-url "https://test.znzmo.com" --headless

  # 安装 Allure 工具
  python run_suite.py --install-allure
        """
    )

    parser.add_argument(
        "-g", "--group",
        type=str,
        help="运行指定分组 (可用分组: 快速检查|核心功能|弹框专项)"
    )
    parser.add_argument(
        "-t", "--tags",
        nargs="*",
        help="运行指定标签的用例 (可用标签: quick|smoke|core|main|popup|ui)"
    )
    parser.add_argument(
        "-l", "--list-groups",
        action="store_true",
        help="列出所有可用的测试分组"
    )
    parser.add_argument(
        "-L", "--list-tags",
        action="store_true",
        help="列出所有可用的测试标签"
    )
    parser.add_argument(
        "--no-allure",
        action="store_true",
        help="禁用 Allure 报告生成"
    )
    parser.add_argument(
        "--no-open-report",
        action="store_true",
        help="生成报告后不自动打开浏览器"
    )
    parser.add_argument(
        "--install-allure",
        action="store_true",
        help="显示 Allure 安装说明"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default="test_suite.yaml",
        help="指定配置文件路径 (默认: test_suite.yaml)"
    )

    # 环境和基础配置参数
    config_group = parser.add_argument_group("环境和基础配置选项")
    config_group.add_argument(
        "--env",
        type=str,
        choices=["dev", "test", "prod"],
        help="测试环境：dev（开发）、test（测试）、prod（生产）（默认：dev）"
    )
    config_group.add_argument(
        "--base-url",
        type=str,
        help="基础 URL（默认：从配置文件读取）"
    )
    config_group.add_argument(
        "--headless",
        action="store_true",
        help="无头模式运行（默认：从配置文件读取）"
    )
    config_group.add_argument(
        "--no-headless",
        action="store_true",
        help="非无头模式运行（默认：从配置文件读取）"
    )

    # 并发执行相关参数
    parallel_group = parser.add_argument_group("并发执行选项")
    parallel_group.add_argument(
        "-p", "--parallel",
        action="store_true",
        dest="force_parallel",
        help="强制启用并发执行"
    )
    parallel_group.add_argument(
        "--no-parallel",
        action="store_true",
        dest="disable_parallel",
        help="禁用并发执行（单进程运行）"
    )
    parallel_group.add_argument(
        "-w", "--workers",
        type=int,
        help="并发进程数（默认：3）"
    )
    parallel_group.add_argument(
        "--dist-mode",
        type=str,
        choices=["file", "class", "function"],
        help="并发分发模式：file（按文件）、class（按类）、function（按函数）（默认：file）"
    )

    # 失败重试相关参数
    retry_group = parser.add_argument_group("失败重试选项")
    retry_group.add_argument(
        "-r", "--reruns",
        type=int,
        help="失败后重试次数（默认：从配置文件读取）"
    )
    retry_group.add_argument(
        "--reruns-delay",
        type=int,
        help="重试间隔时间（秒）（默认：从配置文件读取）"
    )
    retry_group.add_argument(
        "--no-reruns",
        action="store_true",
        dest="disable_reruns",
        help="禁用失败重试功能"
    )
    retry_group.add_argument(
        "--only-flaky",
        action="store_true",
        help="仅对标记为 @pytest.mark.flaky 的用例进行重试"
    )

    args = parser.parse_args()

    if args.install_allure:
        print("安装 Allure 命令行工具:")
        print("\nWindows (使用 Scoop):")
        print("  scoop install allure")
        print("\n其他系统或从官网下载: https://docs.qameta.io/allure/")
        return 0

    # 设置配置相关的环境变量
    if args.env:
        os.environ["TEST_ENV"] = args.env
    if args.base_url:
        os.environ["TEST_BASE_URL"] = args.base_url
    if args.headless:
        os.environ["TEST_HEADLESS"] = "true"
    if args.no_headless:
        os.environ["TEST_HEADLESS"] = "false"

    runner = TestRunner(config_path=args.config)

    if args.list_groups:
        runner.list_groups()
        return 0

    if args.list_tags:
        runner.list_tags()
        return 0

    # 处理并发执行参数
    parallel = None
    if args.force_parallel:
        parallel = True
    elif args.disable_parallel:
        parallel = False

    workers = args.workers
    # 处理失败重试参数
    reruns = args.reruns

    if args.disable_reruns:
        runner.retry_enabled = False
        reruns = 0

    if args.only_flaky:
        runner.retry_only_flaky = True

    if args.group:
        exit_code = runner.run_group(
            args.group, parallel=parallel, workers=workers, reruns=reruns
        )
    elif args.tags:
        exit_code = runner.run_tags(
            args.tags, parallel=parallel, workers=workers, reruns=reruns
        )
    else:
        # 使用 config/settings.py 的默认配置执行
        default_mode = runner._config.execution.default_mode
        if default_mode == "group":
            default_group = runner._config.execution.default_group
            exit_code = runner.run_group(
                default_group, parallel=parallel, workers=workers, reruns=reruns
            )
        elif default_mode == "tags":
            default_tags = runner._config.execution.default_tags
            if default_tags:
                exit_code = runner.run_tags(
                    default_tags, parallel=parallel, workers=workers, reruns=reruns
                )
            else:
                print("错误: 默认标签模式但未配置 default_tags")
                exit_code = 1
        else:
            print(f"错误: 不支持的默认执行模式 '{default_mode}'")
            exit_code = 1

    # 生成报告
    if runner._config.allure.enabled:
        runner.generate_allure_report()

    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
