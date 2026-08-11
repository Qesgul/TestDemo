"""Controlled access to the local test-account pool."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Iterable

import yaml

from common.auth_session import account_cache_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACCOUNT_POOL_PATH = PROJECT_ROOT / "tests" / "data" / "account_pool.yaml"
_TAG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def load_accounts(path: Path = ACCOUNT_POOL_PATH) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list) or not all(isinstance(row, dict) for row in accounts):
        raise ValueError("account_pool.yaml must contain an accounts list")
    return accounts


def find_accounts(required_tags: Iterable[str], *, username: str | None = None) -> list[dict]:
    tags = set(required_tags)
    rows = load_accounts()
    if username:
        rows = [row for row in rows if row.get("username") == username]
    return [row for row in rows if tags.issubset(set(row.get("tags") or []))]


def credential_ref(account: dict) -> str:
    username = str(account.get("username") or "")
    return f"account:{account_cache_id(username)}"


def public_account(account: dict) -> dict:
    return {
        "credential_ref": credential_ref(account),
        "account_traits": list(account.get("tags") or []),
        "description": account.get("description", ""),
    }


def _validate_new_account(account: dict, rows: list[dict]) -> None:
    username = str(account.get("username") or "").strip()
    password = str(account.get("password") or "")
    tags = account.get("tags") or []
    if not username or not password:
        raise ValueError("username and password are required")
    if any(row.get("username") == username for row in rows):
        raise ValueError("username already exists in account_pool.yaml")
    if not tags or not all(isinstance(tag, str) and _TAG_RE.fullmatch(tag) for tag in tags):
        raise ValueError("tags must be non-empty snake_case values")
    if len(set(tags)) != len(tags):
        raise ValueError("tags must not repeat")


def append_account(account: dict, path: Path = ACCOUNT_POOL_PATH) -> None:
    """Append one validated account without rewriting prior YAML entries."""
    rows = load_accounts(path)
    _validate_new_account(account, rows)
    normalized = {
        "username": str(account["username"]).strip(),
        "password": str(account["password"]),
        "tags": list(account["tags"]),
        "description": str(account.get("description") or ""),
        "added_at": str(account.get("added_at") or date.today().isoformat()),
        "added_for": str(account.get("added_for") or ""),
    }
    lines = ["", f'  - username: {json.dumps(normalized["username"], ensure_ascii=False)}',
             f'    password: {json.dumps(normalized["password"], ensure_ascii=False)}', "    tags:"]
    lines.extend(f"      - {tag}" for tag in normalized["tags"])
    lines.extend([
        f'    description: {json.dumps(normalized["description"], ensure_ascii=False)}',
        f'    added_at: {json.dumps(normalized["added_at"], ensure_ascii=False)}',
        f'    added_for: {json.dumps(normalized["added_for"], ensure_ascii=False)}',
        "",
    ])
    content = path.read_text(encoding="utf-8").rstrip() + "\n" + "\n".join(lines)
    parsed = yaml.safe_load(content) or {}
    if len(parsed.get("accounts", [])) != len(rows) + 1:
        raise ValueError("account pool validation failed before write")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
