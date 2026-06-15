#!/usr/bin/env python3
"""校验多 agent 架构：agent frontmatter + 工具白名单 + CLAUDE.md 路由表一致性。
退出码 0 = 全部通过；非 0 = 有失败（打印 FAIL 明细）。"""
import sys, re, pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
CLAUDE_MD = ROOT / "CLAUDE.md"

EXPECTED_AGENTS = {
    "test-design", "auto-case-extract", "auto-planner", "code-engineer",
    "selector-debug", "gio-tracking", "session-recap", "cleanup", "troubleshooter",
}
ALLOWED_TOOLS = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill",
                 "WebSearch", "WebFetch", "Task"}

errors = []

def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    return yaml.safe_load(m.group(1))

def check_agents():
    found = set()
    for md in sorted(AGENTS_DIR.glob("*.md")):
        stem = md.stem
        fm = parse_frontmatter(md.read_text(encoding="utf-8"))
        if fm is None:
            errors.append(f"[{stem}] 缺少 YAML frontmatter")
            continue
        if fm.get("name") != stem:
            errors.append(f"[{stem}] frontmatter name='{fm.get('name')}' 与文件名不符")
        if not str(fm.get("description", "")).strip():
            errors.append(f"[{stem}] description 为空")
        tools_raw = fm.get("tools", "")
        tools = [t.strip() for t in str(tools_raw).split(",") if t.strip()]
        if not tools:
            errors.append(f"[{stem}] tools 为空（需显式最小集）")
        for t in tools:
            if t not in ALLOWED_TOOLS:
                errors.append(f"[{stem}] 未知工具 '{t}'（白名单：{sorted(ALLOWED_TOOLS)}）")
        found.add(stem)
    missing = EXPECTED_AGENTS - found
    extra = found - EXPECTED_AGENTS
    if missing:
        errors.append(f"缺少 agent 文件：{sorted(missing)}")
    if extra:
        errors.append(f"出现未登记 agent：{sorted(extra)}（如有意新增请更新本脚本 EXPECTED_AGENTS）")

def check_route_table():
    if not CLAUDE_MD.exists():
        errors.append("CLAUDE.md 不存在")
        return
    text = CLAUDE_MD.read_text(encoding="utf-8")
    # 路由表区段：从 "Agent 路由表" 标题到下一个二级标题之间
    seg = re.split(r"Agent 路由表", text, maxsplit=1)
    if len(seg) < 2:
        errors.append("CLAUDE.md 缺少『Agent 路由表』区段")
        return
    body = re.split(r"\n##\s", seg[1], maxsplit=1)[0]
    routed = set(re.findall(r"`([a-z-]+)`", body))
    routed &= EXPECTED_AGENTS  # 只看登记内的
    unrouted = EXPECTED_AGENTS - routed
    if unrouted:
        errors.append(f"路由表未覆盖以下 agent：{sorted(unrouted)}")

def main():
    if not AGENTS_DIR.exists():
        errors.append(".claude/agents/ 不存在")
    else:
        check_agents()
    check_route_table()
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print("  - " + e)
        sys.exit(1)
    print(f"VALIDATION PASSED: {len(EXPECTED_AGENTS)} agents + 路由表一致")
    sys.exit(0)

if __name__ == "__main__":
    main()
