#!/usr/bin/env python
"""
Suite-first batch test runner.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, List, Optional

from common.yaml_loader import load_yaml


@dataclass
class SuiteDefinition:
    id: str
    name: str
    description: str = ""
    cases: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def matches_tags(self, tags: set[str]) -> bool:
        if not tags:
            return True
        return bool({tag.strip() for tag in self.tags if tag.strip()} & tags)


@dataclass
class SuiteCatalog:
    default_suite: Optional[str]
    suites: List[SuiteDefinition]

    def get_suite(self, selector: str) -> Optional[SuiteDefinition]:
        normalized = selector.strip()
        for suite in self.suites:
            if normalized in {suite.id, suite.name, *suite.aliases}:
                return suite
        return None


LEGACY_SUITE_ID_MAP = {
    "快速检查": "smoke",
    "核心功能": "core",
    "弹窗专项": "popup",
}


def _normalize_case(case: Any) -> Optional[str]:
    if isinstance(case, str):
        return case.strip() or None
    if isinstance(case, dict):
        file_path = str(case.get("file", "")).strip()
        case_name = str(case.get("case", "")).strip()
        if not file_path:
            return None
        return f"{file_path}::{case_name}" if case_name else file_path
    return None


def _legacy_suite_id(name: str, index: int) -> str:
    return LEGACY_SUITE_ID_MAP.get(name, f"suite_{index}")


def load_suite_catalog(config_path: str = "test_suite.yaml") -> SuiteCatalog:
    payload = load_yaml(config_path) or {}
    suites_payload = payload.get("suites")
    default_suite = payload.get("default_suite")
    suites: List[SuiteDefinition] = []

    if isinstance(suites_payload, list):
        for raw_suite in suites_payload:
            if not isinstance(raw_suite, dict):
                continue
            suite_id = str(raw_suite.get("id", "")).strip()
            name = str(raw_suite.get("name", "")).strip()
            cases = [
                normalized
                for normalized in (_normalize_case(item) for item in raw_suite.get("cases", []))
                if normalized
            ]
            suites.append(
                SuiteDefinition(
                    id=suite_id,
                    name=name or suite_id,
                    description=str(raw_suite.get("description", "")).strip(),
                    cases=cases,
                    tags=[str(tag).strip() for tag in raw_suite.get("tags", []) if str(tag).strip()],
                    aliases=[str(alias).strip() for alias in raw_suite.get("aliases", []) if str(alias).strip()],
                )
            )
    else:
        groups_payload = payload.get("groups", [])
        for index, raw_group in enumerate(groups_payload, start=1):
            if not isinstance(raw_group, dict):
                continue
            name = str(raw_group.get("name", "")).strip()
            suite_id = _legacy_suite_id(name, index)
            cases = [
                normalized
                for normalized in (_normalize_case(item) for item in raw_group.get("cases", []))
                if normalized
            ]
            suites.append(
                SuiteDefinition(
                    id=suite_id,
                    name=name or suite_id,
                    description=str(raw_group.get("description", "")).strip(),
                    cases=cases,
                    tags=[str(tag).strip() for tag in raw_group.get("tags", []) if str(tag).strip()],
                    aliases=[name] if name else [],
                )
            )
        if default_suite is None:
            default_suite = _legacy_suite_id(str(payload.get("default_group", "核心功能")), 0)

    if default_suite is None and suites:
        default_suite = suites[0].id

    for suite in suites:
        if not suite.id:
            raise ValueError(f"Suite missing id: {suite}")
        if not suite.cases:
            raise ValueError(f"Suite '{suite.id}' has no cases configured")

    return SuiteCatalog(default_suite=str(default_suite) if default_suite else None, suites=suites)


class SuiteRunner:
    def __init__(self, config_path: str = "test_suite.yaml"):
        self.config_path = config_path
        self.catalog = load_suite_catalog(config_path)
        from config.settings import get_config

        self.app_config = get_config()
        self.base_command = [sys.executable, "-m", "pytest", "-v", "-s"]

    @property
    def default_suite(self) -> Optional[str]:
        return self.catalog.default_suite or self.app_config.execution.default_suite

    def list_suites(self, tags: Optional[List[str]] = None) -> str:
        tag_filter = {tag.strip() for tag in (tags or []) if tag.strip()}
        lines = ["Available suites:"]
        if tag_filter:
            lines.append(f"Filter tags: {', '.join(sorted(tag_filter))}")

        matched = [suite for suite in self.catalog.suites if suite.matches_tags(tag_filter)]
        if not matched:
            lines.append("(no matching suites)")
            return "\n".join(lines)

        for suite in matched:
            tag_text = ", ".join(suite.tags) if suite.tags else "-"
            default_mark = " [default]" if suite.id == self.default_suite else ""
            lines.append(
                f"- {suite.id}{default_mark}: {suite.name} | cases={len(suite.cases)} | tags={tag_text}"
            )
            lines.append(f"  {suite.description or '-'}")
            lines.append(f"  Try: python run_suite.py run {suite.id}")
        return "\n".join(lines)

    def show_suite(self, selector: str) -> str:
        suite = self._require_suite(selector)
        tag_text = ", ".join(suite.tags) if suite.tags else "-"
        lines = [
            f"Suite: {suite.id}",
            f"Name: {suite.name}",
            f"Description: {suite.description or '-'}",
            f"Tags: {tag_text}",
            f"Cases: {len(suite.cases)}",
            "Default strategy:",
            f"  env={self.app_config.env.value}",
            f"  workers={self.app_config.execution.parallel_workers}",
            f"  reruns={self.app_config.execution.retry_max_reruns}",
            f"  headless={self.app_config.current_env.headless}",
            f"  allure={self.app_config.allure.enabled}",
            "Case list:",
        ]
        lines.extend(f"  - {case}" for case in suite.cases)
        lines.append("Common commands:")
        lines.append(f"  python run_suite.py run {suite.id}")
        lines.append(f"  python run_suite.py run {suite.id} --serial")
        lines.append(f"  python run_suite.py run {suite.id} --workers 4")
        return "\n".join(lines)

    def build_run_command(
        self,
        selector: str,
        *,
        tags: Optional[List[str]] = None,
        workers: Optional[int] = None,
        serial: bool = False,
        reruns: Optional[int] = None,
        no_reruns: bool = False,
        allure_enabled: Optional[bool] = None,
    ) -> List[str]:
        suite = self._require_suite(selector)
        command = list(self.base_command)

        effective_workers = 1 if serial else (workers or self.app_config.execution.parallel_workers)
        parallel_enabled = (not serial) and self.app_config.execution.parallel_enabled and effective_workers > 1
        if parallel_enabled:
            command.extend(["-n", str(effective_workers)])

        retry_enabled = self.app_config.execution.retry_enabled and not no_reruns
        effective_reruns = reruns if reruns is not None else self.app_config.execution.retry_max_reruns
        if retry_enabled:
            command.extend(["--max-reruns", str(effective_reruns)])

        enable_allure = self.app_config.allure.enabled if allure_enabled is None else allure_enabled
        if enable_allure:
            command.extend(["--alluredir", self.app_config.allure.results_dir, "--clean-alluredir"])

        if tags:
            command.extend(["-m", " or ".join(tag.strip() for tag in tags if tag.strip())])

        command.extend(suite.cases)
        return command

    def run(
        self,
        selector: str,
        *,
        tags: Optional[List[str]] = None,
        workers: Optional[int] = None,
        serial: bool = False,
        reruns: Optional[int] = None,
        no_reruns: bool = False,
        allure_enabled: Optional[bool] = None,
    ) -> int:
        command = self.build_run_command(
            selector,
            tags=tags,
            workers=workers,
            serial=serial,
            reruns=reruns,
            no_reruns=no_reruns,
            allure_enabled=allure_enabled,
        )
        env = os.environ.copy()
        if tags:
            env["TEST_TAGS"] = ",".join(tag.strip() for tag in tags if tag.strip())
        print(f"Running suite: {self._require_suite(selector).id}")
        print(f"Command: {' '.join(command)}")
        process = subprocess.run(command, env=env)
        if process.returncode == 0:
            self.generate_allure_report(allure_enabled=allure_enabled)
        return process.returncode

    def generate_allure_report(self, *, allure_enabled: Optional[bool] = None) -> None:
        enable_allure = self.app_config.allure.enabled if allure_enabled is None else allure_enabled
        if not enable_allure:
            return

        results_dir = self.app_config.allure.results_dir
        report_dir = self.app_config.allure.report_dir
        if not os.path.exists(results_dir) or not os.listdir(results_dir):
            print("No Allure results found, skipping report generation.")
            return

        allure_bin = shutil.which("allure")
        if not allure_bin:
            print("Warning: allure command not found, skipping report generation.")
            return

        generate_command = [
            allure_bin,
            "generate",
            results_dir,
            "-o",
            report_dir,
            "--clean",
            "--title",
            self.app_config.allure.report_title,
        ]
        result = subprocess.run(generate_command)
        if result.returncode != 0:
            print("Warning: failed to generate Allure report.")
            return

        if self.app_config.allure.open_report:
            subprocess.run([allure_bin, "open", report_dir])

    def resolve_deprecated_group(self, group_name: str) -> str:
        with contextlib.suppress(ValueError):
            return self._require_suite(group_name).id
        return _legacy_suite_id(group_name, 0)

    def _require_suite(self, selector: str) -> SuiteDefinition:
        suite = self.catalog.get_suite(selector)
        if suite is None:
            raise ValueError(f"Unknown suite: {selector}")
        return suite


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Suite-first batch test runner",
        epilog=(
            "Most common commands:\n"
            "  python run_suite.py list\n"
            "  python run_suite.py show core\n"
            "  python run_suite.py run core\n"
            "\n"
            "Suite model:\n"
            "  suite = what to run\n"
            "  options = how to run it\n"
            "\n"
            "Advanced filters:\n"
            "  python run_suite.py run core --tags popup\n"
            "  python run_suite.py run core --workers 4 --reruns 3\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="test_suite.yaml", help="Suite config path")
    parser.add_argument("--group", help=argparse.SUPPRESS)
    parser.add_argument("--list-groups", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--list-tags", action="store_true", help=argparse.SUPPRESS)
    _add_run_options(parser, suppress_help=True)

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List available suites")
    list_parser.add_argument("--tags", nargs="+", help="Show suites related to these tags")

    show_parser = subparsers.add_parser("show", help="Show suite details")
    show_parser.add_argument("suite", help="Suite id")

    run_parser = subparsers.add_parser("run", help="Run a suite")
    run_parser.add_argument("suite", nargs="?", help="Suite id")
    _add_run_options(run_parser, suppress_help=False)

    return parser


def _add_run_options(parser: argparse.ArgumentParser, *, suppress_help: bool) -> None:
    help_text = argparse.SUPPRESS if suppress_help else None
    parser.add_argument("--tags", nargs="+", help=help_text or "Extra pytest tag filter within the suite")
    parser.add_argument("--workers", type=int, help=help_text or "Override worker count")
    parser.add_argument("--serial", action="store_true", help=help_text or "Force serial execution")
    parser.add_argument("--reruns", type=int, help=help_text or "Override rerun count")
    parser.add_argument("--no-reruns", action="store_true", help=help_text or "Disable reruns")
    parser.add_argument("--env", choices=["dev", "test", "prod"], help=help_text or "Execution environment")
    parser.add_argument("--base-url", help=help_text or "Base URL override")
    parser.add_argument("--headless", action="store_true", help=help_text or "Run headless")
    parser.add_argument("--headed", action="store_true", help=help_text or "Run headed")
    parser.add_argument("--allure", action="store_true", help=help_text or "Force enable Allure report")
    parser.add_argument("--no-allure", action="store_true", help=help_text or "Disable Allure report")
    parser.add_argument("--open-report", action="store_true", help=help_text or "Open Allure report after generation")
    parser.add_argument("--no-open-report", action="store_true", help=help_text or "Do not open Allure report")


def _apply_runtime_env(args: argparse.Namespace) -> None:
    if getattr(args, "env", None):
        os.environ["TEST_ENV"] = args.env
    if getattr(args, "base_url", None):
        os.environ["TEST_BASE_URL"] = args.base_url
    if getattr(args, "headless", False):
        os.environ["TEST_HEADLESS"] = "true"
    if getattr(args, "headed", False):
        os.environ["TEST_HEADLESS"] = "false"


def _print_deprecated_mapping(old: str, new: str) -> None:
    print(f"[DEPRECATED] {old} -> {new}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _apply_runtime_env(args)
    runner = SuiteRunner(config_path=args.config)

    if args.list_groups:
        _print_deprecated_mapping("--list-groups", "list")
        args.command = "list"
    elif args.group:
        resolved_suite = runner.resolve_deprecated_group(args.group)
        _print_deprecated_mapping(f"--group {args.group}", f"run {resolved_suite}")
        args.command = "run"
        args.suite = resolved_suite
    elif args.list_tags:
        _print_deprecated_mapping("--list-tags", "list --tags <tag>")
        args.command = "list"

    if args.command is None:
        args.command = "run"

    if args.command == "list":
        print(runner.list_suites(tags=getattr(args, "tags", None)))
        return 0

    if args.command == "show":
        try:
            print(runner.show_suite(args.suite))
            return 0
        except ValueError as exc:
            print(str(exc))
            return 1

    suite_selector = getattr(args, "suite", None) or runner.default_suite
    if not suite_selector:
        print("No suite provided and no default suite configured.")
        return 1

    if getattr(args, "open_report", False):
        runner.app_config.allure.open_report = True
    if getattr(args, "no_open_report", False):
        runner.app_config.allure.open_report = False

    allure_enabled: Optional[bool] = None
    if getattr(args, "allure", False):
        allure_enabled = True
    if getattr(args, "no_allure", False):
        allure_enabled = False

    try:
        return runner.run(
            suite_selector,
            tags=getattr(args, "tags", None),
            workers=getattr(args, "workers", None),
            serial=getattr(args, "serial", False),
            reruns=getattr(args, "reruns", None),
            no_reruns=getattr(args, "no_reruns", False),
            allure_enabled=allure_enabled,
        )
    except ValueError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
