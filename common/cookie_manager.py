"""
Cookie storage and reuse helpers for login flows.
"""

import json
import logging
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from playwright.sync_api import BrowserContext, Page

from common.browser_manager import BrowserManager
from config.settings import get_config


class CookieManager:
    @classmethod
    def _config(cls):
        return get_config()

    @classmethod
    def _cookie_dir(cls) -> Path:
        return Path(cls._config().cookie_dir)

    @classmethod
    def _sanitize_filename(cls, filename: str) -> str:
        import re

        return re.sub(r'[<>:"/\\|?*@]', "_", filename)

    @classmethod
    def _get_cookie_filename(cls, account_identifier: str, env: str = None) -> str:
        current_env = env or cls._config().env.value
        safe_account_id = cls._sanitize_filename(account_identifier)
        filename = f"cookies_{current_env}_{safe_account_id}.json"
        return str(cls._cookie_dir() / filename)

    @classmethod
    def save_cookies(
        cls,
        account_identifier: str,
        context: BrowserContext,
        env: str = None,
    ) -> None:
        cookie_data = {
            "account_identifier": account_identifier,
            "env": env or cls._config().env.value,
            "timestamp": datetime.now().isoformat(),
            "cookies": context.cookies(),
        }

        cls._cookie_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
        filename = cls._get_cookie_filename(account_identifier, env)
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2, default=str)
            os.chmod(filename, stat.S_IRUSR | stat.S_IWUSR)
        except Exception as e:
            raise RuntimeError(f"Failed to save cookies: {e}") from e

    @classmethod
    def load_cookies(
        cls,
        account_identifier: str,
        env: str = None,
    ) -> Optional[Dict[str, Any]]:
        filename = cls._get_cookie_filename(account_identifier, env)
        if not os.path.exists(filename):
            return None

        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load cookies: {e}") from e

    @classmethod
    def delete_cookies(cls, account_identifier: str, env: str = None) -> bool:
        filename = cls._get_cookie_filename(account_identifier, env)
        if os.path.exists(filename):
            try:
                os.remove(filename)
                return True
            except Exception as e:
                raise RuntimeError(f"Failed to delete cookie file: {e}") from e
        return False

    @classmethod
    def is_cookie_valid(
        cls,
        cookie_data: Dict[str, Any],
        max_age_hours: int = 24,
    ) -> bool:
        if "timestamp" not in cookie_data or "cookies" not in cookie_data:
            return False

        try:
            timestamp = datetime.fromisoformat(cookie_data["timestamp"])
            if datetime.now() - timestamp > timedelta(hours=max_age_hours):
                return False
            return bool(cookie_data["cookies"])
        except Exception as e:
            raise RuntimeError(f"Failed to validate cookies: {e}") from e

    @classmethod
    def set_cookies_to_context(
        cls,
        context: BrowserContext,
        cookie_data: Dict[str, Any],
        base_url: str = None,
    ) -> None:
        if base_url is None:
            base_url = cls._config().current_env.base_url

        try:
            from urllib.parse import urlparse

            parsed_url = urlparse(base_url)
            domain = parsed_url.netloc
        except Exception as e:
            raise RuntimeError(f"Failed to parse base URL: {e}") from e

        processed_cookies = []
        for cookie in cookie_data["cookies"]:
            new_cookie = cookie.copy()
            if not new_cookie.get("domain"):
                new_cookie["domain"] = domain
            if not new_cookie.get("path"):
                new_cookie["path"] = "/"
            if "name" not in new_cookie or "value" not in new_cookie:
                continue

            if "expires" in new_cookie:
                try:
                    if isinstance(new_cookie["expires"], str):
                        dt = datetime.fromisoformat(
                            new_cookie["expires"].replace("Z", "+00:00")
                        )
                        new_cookie["expires"] = int(dt.timestamp())
                    elif isinstance(new_cookie["expires"], float):
                        new_cookie["expires"] = int(new_cookie["expires"])
                except Exception:
                    del new_cookie["expires"]

            for key in list(new_cookie.keys()):
                if key not in {
                    "name",
                    "value",
                    "domain",
                    "path",
                    "expires",
                    "httpOnly",
                    "secure",
                    "sameSite",
                }:
                    del new_cookie[key]

            processed_cookies.append(new_cookie)

        if processed_cookies:
            try:
                context.add_cookies(processed_cookies)
            except Exception:
                for cookie in processed_cookies:
                    try:
                        context.add_cookies([cookie])
                    except Exception as e:
                        logger.warning("注入 cookie '%s' 失败: %s", cookie.get("name"), e)
                        continue

    @classmethod
    def login_with_cookie(
        cls,
        account_identifier: str,
        login_func: callable,
        page: Page = None,
        env: str = None,
        max_age_hours: int = 24,
    ) -> Page:
        if page is None:
            page = BrowserManager.create_page()
        context = page.context

        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                context.clear_cookies()
                cls.set_cookies_to_context(context, cookie_data)
                page.reload()
                return page
            except Exception as e:
                logger.warning("Cookie 恢复失败，回退至重新登录（account=%s）: %s", account_identifier, e)

        login_func(page)
        cls.save_cookies(account_identifier, context, env)
        return page

    @classmethod
    def login_with_cookie_by_context(
        cls,
        account_identifier: str,
        login_func: callable,
        context: BrowserContext,
        env: str = None,
        max_age_hours: int = 24,
    ) -> Page:
        config = cls._config()
        page = context.new_page()
        page.set_default_timeout(config.current_env.default_timeout_ms)
        page.goto(config.current_env.base_url)

        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                context.clear_cookies()
                cls.set_cookies_to_context(context, cookie_data)
                page.reload()
                return page
            except Exception as e:
                logger.warning("Cookie 恢复失败，回退至重新登录（account=%s）: %s", account_identifier, e)

        login_func(page)
        cls.save_cookies(account_identifier, context, env)
        return page

    @classmethod
    def get_all_cookie_files(cls, env: str = None) -> list[str]:
        current_env = env or cls._config().env.value
        cookie_dir = cls._cookie_dir()
        if not cookie_dir.exists():
            return []

        cookie_files = []
        for filename in os.listdir(cookie_dir):
            if filename.startswith(f"cookies_{current_env}_") and filename.endswith(".json"):
                cookie_files.append(str(cookie_dir / filename))
        return cookie_files

    @classmethod
    def delete_all_cookies(cls, env: str = None) -> int:
        cookie_files = cls.get_all_cookie_files(env)
        count = 0
        for file_path in cookie_files:
            try:
                os.remove(file_path)
                count += 1
            except Exception:
                continue
        return count

    @classmethod
    def validate_and_use_cookie(
        cls,
        account_identifier: str,
        context: BrowserContext,
        env: str = None,
        max_age_hours: int = 24,
    ) -> bool:
        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                cls.set_cookies_to_context(context, cookie_data)
                return True
            except Exception:
                return False
        return False
