"""
快照比较工具 - 动态列表数据的持久化与差量比对。

用途：
  - 每次测试将采集到的列表数据写入数据 YAML 文件的 snapshots 键。
  - 若快照已存在，打印本次 vs 上次的差量报告（新增/减少/不变条目数）。
  - 以快照上下文给出更有意义的存在性断言（替代裸 len >= 1）。

典型用法（YAML 模式，推荐）：
  prev = load_snapshot_from_yaml("tests/data/xxx_data.yaml")
  ...  # 采集数据
  snap = {"rank_3d": items_a, "su_model": items_b}
  compare_and_print("rank_3d",  prev.get("rank_3d",  []), snap["rank_3d"])
  compare_and_print("su_model", prev.get("su_model", []), snap["su_model"])
  assert_not_empty("3D爆款榜", snap["rank_3d"], prev.get("rank_3d", []), assertion)
  save_snapshot_to_yaml("tests/data/xxx_data.yaml", snap)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# 项目根目录（common/ 的上级），用于解析相对路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: str) -> Path:
    """将相对路径转为绝对路径（相对于项目根）。"""
    p = Path(path)
    return p if p.is_absolute() else _PROJECT_ROOT / p


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_snapshot(path: str) -> dict[str, Any]:
    """加载上次快照；文件不存在或 JSON 解析失败时返回空字典（首次运行场景）。"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_snapshot(path: str, data: dict[str, list[str]]) -> None:
    """将本次采集数据写入快照文件（覆盖上次，自动创建目录）。

    文件格式：
      {
        "captured_at": "2026-05-25T10:30:00",
        "data": {
          "rank_3d": ["作品A", "作品B", ...],
          ...
        }
      }
    """
    payload: dict[str, Any] = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
    }
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    [快照] 已更新 -> {path}  (共 {len(data)} 个数据项)")


# ---------------------------------------------------------------------------
# 差量比对
# ---------------------------------------------------------------------------

def compare_and_print(key: str, previous: list[str], current: list[str]) -> None:
    """比较两次采集的列表，打印差量报告（新增 / 减少 / 不变）。

    Args:
        key:      数据项名称，用于日志标识。
        previous: 上次快照中的列表（首次运行时为空列表）。
        current:  本次采集的列表。
    """
    if not previous:
        print(f"    [{key}] 首次采集，共 {len(current)} 条，已作为基准保存")
        return

    prev_set = set(previous)
    curr_set = set(current)
    added   = sorted(curr_set - prev_set)
    removed = sorted(prev_set - curr_set)
    same    = len(prev_set & curr_set)

    print(f"    [{key}] 上次 {len(previous)} 条 -> 本次 {len(current)} 条")

    if not added and not removed:
        print(f"      = 与上次完全一致（{same} 条不变）")
        return

    if added:
        preview = [f'"{t[:25]}"' for t in added[:3]]
        suffix  = f"  ...共 {len(added)} 条" if len(added) > 3 else ""
        print(f"      + 新增: {', '.join(preview)}{suffix}")
    if removed:
        preview = [f'"{t[:25]}"' for t in removed[:3]]
        suffix  = f"  ...共 {len(removed)} 条" if len(removed) > 3 else ""
        print(f"      - 减少: {', '.join(preview)}{suffix}")
    if same:
        print(f"      = 不变: {same} 条")


# ---------------------------------------------------------------------------
# 存在性断言（替代裸 len >= 1）
# ---------------------------------------------------------------------------

def assert_not_empty(
    label: str,
    current: list[str],
    previous: list[str],
    assertion: Any,
) -> None:
    """数据存在性断言；为空时结合快照上下文给出有意义的错误信息。

    - 若本次采集到数据 → 直接通过，无任何输出。
    - 若本次为空、但上次有数据 → 断言失败：「数据消失」。
    - 若本次为空、且无历史快照   → 断言失败：「首次采集即为空」。

    Args:
        label:     显示在断言消息中的数据项描述（如「3D爆款榜」）。
        current:   本次采集的列表。
        previous:  上次快照中的列表（首次运行时传 []）。
        assertion: pytest 的 assertion fixture，需提供 assert_true(cond, message) 方法。
    """
    if current:
        return  # 有数据，直接通过

    if previous:
        assertion.assert_true(
            False,
            message=(
                f"「{label}」数据消失：上次采集到 {len(previous)} 条，本次 0 条，"
                "请检查页面渲染是否正常或选择器是否失效"
            ),
        )
    else:
        assertion.assert_true(
            False,
            message=f"「{label}」首次采集即为空，页面数据未加载或选择器失效",
        )


# ---------------------------------------------------------------------------
# YAML 数据文件内嵌快照（推荐方式）
# ---------------------------------------------------------------------------

def load_snapshot_from_yaml(yaml_path: str) -> dict[str, Any]:
    """从 YAML 数据文件的 snapshots 键读取上次快照（首次运行或解析失败时返回 {}）。

    文件结构示例::

        expected_search_keyword: "..."
        snapshots:
          captured_at: "2026-05-26T09:00:00"
          rank_3d:
            - "1 | 法式复古客餐厅 | 109216 | 172-222元"
            - ...
    """
    try:
        raw = yaml.safe_load(_resolve(yaml_path).read_text(encoding="utf-8")) or {}
        snap = raw.get("snapshots") or {}
        # 去掉 captured_at 等元数据键，只返回列表数据
        return {k: v for k, v in snap.items() if k != "captured_at"}
    except Exception:
        return {}


def save_snapshot_to_yaml(yaml_path: str, data: dict[str, list]) -> None:
    """将快照数据写入 YAML 数据文件的 snapshots 键，其余内容（含注释）原样保留。

    实现策略：
      - 以文本方式读文件，找到 "snapshots:" 所在行，截断其后内容；
      - 将新快照序列化为 YAML 块并追加到文件末尾。
      - 若文件不存在则直接创建。

    Args:
        yaml_path: 数据文件路径（相对于项目根或绝对路径）。
        data:      本次采集数据，格式 {key: [str, ...], ...}。
    """
    path = _resolve(yaml_path)

    # ① 读原始文本（保留注释/格式）
    existing_text = path.read_text(encoding="utf-8") if path.exists() else ""

    # ② 找 "snapshots:" 行并截断，保留其上方全部内容
    lines = existing_text.splitlines(keepends=True)
    cut_index: int | None = None
    for idx, line in enumerate(lines):
        if line.startswith("snapshots:"):
            cut_index = idx
            break
    header_text = "".join(lines[:cut_index]) if cut_index is not None else existing_text.rstrip("\n") + "\n"

    # ③ 序列化新快照块
    snapshot_payload: dict[str, Any] = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        **data,
    }
    snap_yaml = yaml.dump(
        {"snapshots": snapshot_payload},
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )

    # ④ 拼接写回
    path.write_text(header_text + "\n" + snap_yaml, encoding="utf-8")
    print(f"    [快照] 已写入 {yaml_path} → snapshots 键（共 {len(data)} 个数据项）")
