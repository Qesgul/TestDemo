#!/usr/bin/env python3
"""Executable account-session provider for Rapid QA and pytest runs."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



def _dependencies():
    # Import only after argparse has handled this CLI. Importing ``common`` runs
    # the project's global test configuration, whose own argparse parser treats
    # ``--help`` as a process-wide request.
    from common.account_pool import append_account, credential_ref, find_accounts, public_account
    from common.auth_session import resolve_auth_profile

    return append_account, credential_ref, find_accounts, public_account, resolve_auth_profile


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def resolve(args: argparse.Namespace) -> tuple[dict | None, dict]:
    _, _, find_accounts, public_account, resolve_auth_profile = _dependencies()
    accounts = find_accounts(args.require_tag, username=getattr(args, "username", None))
    base = {"auth_scope": resolve_auth_profile(args.url).scope, "required_tags": args.require_tag}
    if not accounts:
        return None, {**base, "status": "NEEDS_ACCOUNT", "candidates": []}
    if len(accounts) > 1:
        return None, {**base, "status": "NEEDS_DECISION", "candidates": [public_account(row) for row in accounts]}
    return accounts[0], base


def command_resolve(args: argparse.Namespace) -> int:
    account, payload = resolve(args)
    if account is not None:
        _, credential_ref, _, _, _ = _dependencies()
        payload = {
            **payload,
            "status": "MATCHED",
            "credential_ref": credential_ref(account),
            "account_traits": list(account.get("tags") or []),
        }
    emit(payload)
    return 0


def command_prepare(args: argparse.Namespace) -> int:
    account, payload = resolve(args)
    if account is None:
        emit(payload)
        return 0
    try:
        # Import lazily: the project's settings module parses process arguments
        # during import, which would otherwise hijack this CLI's --help.
        from common.selector_finder.login_session import ensure_storage_state

        state_path = Path(ensure_storage_state(args.url, account["username"], account["password"], headless=args.headless))
        _, credential_ref, _, _, resolve_auth_profile = _dependencies()
        profile = resolve_auth_profile(args.url)
        expires_at = datetime.fromtimestamp(state_path.stat().st_mtime, timezone.utc) + timedelta(hours=profile.state_ttl_hours)
        emit({
            **payload,
            "status": "READY",
            "credential_ref": credential_ref(account),
            "account_traits": list(account.get("tags") or []),
            "storage_state_path": str(state_path),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        })
        return 0
    except Exception as exc:
        emit({**payload, "status": "BLOCKED", "reason": type(exc).__name__})
        return 1


def command_register(_: argparse.Namespace) -> int:
    print("账号将仅写入本地 account_pool.yaml；密码不会显示或输出。")
    username = input("账号：").strip()
    password = getpass.getpass("密码：")
    tags = [item.strip() for item in input("标签（逗号分隔，snake_case）：").split(",") if item.strip()]
    description = input("用途说明：").strip()
    added_for = input("关联需求/用例：").strip()
    summary = {"username": username, "tags": tags, "description": description, "added_for": added_for}
    print("待写入摘要（不含密码）：" + json.dumps(summary, ensure_ascii=False))
    if input("确认写入？[y/N]：").strip().lower() not in {"y", "yes"}:
        emit({"status": "CANCELLED"})
        return 0
    try:
        append_account, _, _, _, _ = _dependencies()
        append_account({**summary, "password": password})
        emit({"status": "REGISTERED", "credential_ref": "account:registered", "account_traits": tags})
        return 0
    except Exception as exc:
        emit({"status": "BLOCKED", "reason": type(exc).__name__})
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("resolve", command_resolve), ("prepare", command_prepare)):
        command = subs.add_parser(name)
        command.add_argument("--url", required=True)
        command.add_argument("--require-tag", action="append", default=[])
        command.add_argument("--username")
        command.add_argument("--headless", action="store_true")
        command.set_defaults(handler=handler)
    register = subs.add_parser("register", help="Interactively append one local test account")
    register.set_defaults(handler=command_register)
    return parser


if __name__ == "__main__":
    parsed = build_parser().parse_args()
    raise SystemExit(parsed.handler(parsed))
