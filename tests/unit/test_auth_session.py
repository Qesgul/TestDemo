# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from common.auth_session import (
    account_cache_id,
    resolve_auth_profile,
    state_path_for,
)


def test_resolve_material_profile_for_com_subdomain():
    profile = resolve_auth_profile("https://su.znzmo.com/sumoxing/1.html")
    assert profile.name == "material"
    assert profile.scope == "znzmo_com"


def test_resolve_ai_draw_profile_for_cn_site():
    profile = resolve_auth_profile("https://ai.znzmo.cn/community/AIDrawPage.html")
    assert profile.name == "ai_draw"
    assert profile.scope == "ai_znzmo_cn"


def test_resolve_unknown_domain_fails_fast():
    with pytest.raises(ValueError):
        resolve_auth_profile("https://example.com/")


def test_state_paths_are_isolated_by_auth_scope(tmp_path: Path):
    account = "17768100279"
    material = state_path_for("https://su.znzmo.com/a", account, state_dir=tmp_path)
    ai_draw = state_path_for("https://ai.znzmo.cn/a", account, state_dir=tmp_path)

    assert material != ai_draw
    assert "znzmo_com" in material.name
    assert "ai_znzmo_cn" in ai_draw.name
    assert account not in material.name
    assert account_cache_id(account) in material.name
