"""Unit tests for yaml_reuse.find_existing_batch."""
from pathlib import Path

import pytest
import yaml as pyyaml

from common.selector_finder.yaml_reuse import find_existing_batch
from common.selector_finder.models import LocatorSpec


@pytest.fixture
def yaml_dir(tmp_path: Path) -> Path:
    """构造一个含 2 个 yaml 文件的目录。"""
    d = tmp_path / "elements"
    d.mkdir()

    (d / "ai_draw_elements.yaml").write_text(
        pyyaml.safe_dump({
            "step1_点击家装": {"type": "role", "role": "button", "name": "家装"},
            "step2_生成按钮": {"type": "css", "selector": "#OperationForm-btnSubmit"},
        }, allow_unicode=True),
        encoding="utf-8",
    )
    (d / "login_elements.yaml").write_text(
        pyyaml.safe_dump({
            "用户名输入框": {"type": "placeholder", "placeholder": "请输入手机号"},
        }, allow_unicode=True),
        encoding="utf-8",
    )
    return d


def test_empty_descs_returns_empty_dict(yaml_dir: Path) -> None:
    assert find_existing_batch([], str(yaml_dir)) == {}


def test_no_match_returns_empty_dict(yaml_dir: Path) -> None:
    result = find_existing_batch(["完全不存在的元素描述"], str(yaml_dir))
    assert result == {}


def test_exact_match_via_normalization(yaml_dir: Path) -> None:
    # "点击家装" 规范化后等于 "step1_点击家装" 去 step1_ 前缀
    result = find_existing_batch(["点击家装"], str(yaml_dir))
    assert "点击家装" in result
    spec, action = result["点击家装"]
    assert isinstance(spec, LocatorSpec)
    assert spec.strategy == "role"
    assert spec.role == "button"
    assert spec.name == "家装"
    assert action is None


def test_partial_hit_only_returns_hit_descs(yaml_dir: Path) -> None:
    descs = ["点击家装", "完全不存在的元素", "生成按钮"]
    result = find_existing_batch(descs, str(yaml_dir))
    assert set(result.keys()) == {"点击家装", "生成按钮"}


def test_cross_yaml_file_match(yaml_dir: Path) -> None:
    # 用户名输入框 在 login_elements.yaml
    result = find_existing_batch(["用户名输入框"], str(yaml_dir))
    assert "用户名输入框" in result
    spec, _ = result["用户名输入框"]
    assert spec.strategy == "placeholder"


def test_step_prefix_in_input_is_stripped(yaml_dir: Path) -> None:
    # 输入含 step5_ 前缀，应能匹配上 yaml 中含 step1_ 前缀的 key
    result = find_existing_batch(["step5_点击家装"], str(yaml_dir))
    assert "step5_点击家装" in result


def test_nonexistent_yaml_dir_returns_empty(tmp_path: Path) -> None:
    result = find_existing_batch(["any"], str(tmp_path / "does_not_exist"))
    assert result == {}


def test_action_field_propagates(tmp_path: Path) -> None:
    d = tmp_path / "elements"
    d.mkdir()
    (d / "upload_elements.yaml").write_text(
        pyyaml.safe_dump({
            "上传按钮": {"type": "css", "selector": "input[type='file']", "action": "upload"},
        }, allow_unicode=True),
        encoding="utf-8",
    )
    result = find_existing_batch(["上传按钮"], str(d))
    _, action = result["上传按钮"]
    assert action == "upload"
