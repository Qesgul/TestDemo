# -*- coding: utf-8 -*-
"""Authentication profiles and cache naming for Znzmo sites."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from common.yaml_loader import load_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUTH_DIR = PROJECT_ROOT / ".auth"


@dataclass(frozen=True)
class AuthProfile:
    """A login boundary that must not share cached state with other profiles."""

    name: str
    scope: str
    home_url: str
    login_strategy: str
    state_ttl_hours: float = 12


MATERIAL_PROFILE = AuthProfile(
    name="material",
    scope="znzmo_com",
    home_url="https://su.znzmo.com/sumoxing/1200607583.html",
    login_strategy="su_ui",
)

AI_DRAW_PROFILE = AuthProfile(
    name="ai_draw",
    scope="ai_znzmo_cn",
    home_url="https://ai.znzmo.cn/community/AIDrawPage.html?menuKey=home",
    login_strategy="ai_draw_ui",
)


def resolve_auth_profile(url: str) -> AuthProfile:
    """Return the authentication profile for a target URL.

    Unknown targets fail fast so automation does not guess a cross-domain login.
    """
    host = (urlparse(url).hostname or "").lower()
    if host == "ai.znzmo.cn" or host.endswith(".ai.znzmo.cn"):
        return AI_DRAW_PROFILE
    if host == "znzmo.com" or host.endswith(".znzmo.com"):
        return MATERIAL_PROFILE
    raise ValueError(f"Unsupported auth target domain: {host or url}")


def account_cache_id(account_identifier: str) -> str:
    """Create a stable, non-secret account id for cache filenames."""
    return hashlib.sha256(account_identifier.encode("utf-8")).hexdigest()[:12]


def state_path_for(
    url: str,
    account_identifier: str,
    *,
    state_dir: Optional[Path] = None,
) -> Path:
    profile = resolve_auth_profile(url)
    auth_dir = state_dir or DEFAULT_AUTH_DIR
    safe_env = "dev"
    safe_account = account_cache_id(account_identifier)
    return auth_dir / f"{safe_env}_{profile.scope}_{safe_account}_state.json"


def load_default_account() -> Optional[dict]:
    """Read the default test account from account_pool.yaml.

    Runtime auth should prefer this file over legacy login_data.yaml.
    """
    data = load_yaml("tests/data/account_pool.yaml") or {}
    accounts = data.get("accounts") or []
    for account in accounts:
        if "default" in (account.get("tags") or []):
            return account
    return accounts[0] if accounts else None


def sanitize_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*@]', "_", value)
