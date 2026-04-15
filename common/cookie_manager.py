"""
Cookie管理器 - 用于管理登录Cookie的存储、读取和验证

功能特性：
1. 按账号和环境存储Cookie到本地JSON文件
2. 支持Cookie有效性验证
3. 与Playwright框架集成，自动处理Cookie的设置和获取
4. 支持多环境（dev/test/prod）的Cookie管理
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from playwright.sync_api import BrowserContext, Page
from config.settings import config
from common.browser_manager import BrowserManager


class CookieManager:
    """
    Cookie管理器 - 负责Cookie的存储、读取和验证

    每个账号的Cookie会按环境存储在单独的JSON文件中，文件命名格式：
    cookies_{env}_{account_identifier}.json
    """

    # Cookie存储目录（可配置，默认使用项目根目录下 core/）
    COOKIE_DIR = Path(config.cookie_dir)

    @classmethod
    def _sanitize_filename(cls, filename: str) -> str:
        """
        清理文件名中的非法字符

        Args:
            filename: 原始文件名

        Returns:
            清理后的安全文件名
        """
        import re
        sanitized = re.sub(r'[<>:"/\\|?*@]', "_", filename)
        return sanitized

    @classmethod
    def _get_cookie_filename(cls, account_identifier: str, env: str = None) -> str:
        if env is None:
            env = config.env.value

        safe_account_id = cls._sanitize_filename(account_identifier)
        filename = f"cookies_{env}_{safe_account_id}.json"
        return str(cls.COOKIE_DIR / filename)

    @classmethod
    def save_cookies(cls, account_identifier: str, context: BrowserContext, env: str = None) -> None:
        cookies = context.cookies()
        cookie_data = {
            "account_identifier": account_identifier,
            "env": env or config.env.value,
            "timestamp": datetime.now().isoformat(),
            "cookies": cookies,
        }

        cls.COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        filename = cls._get_cookie_filename(account_identifier, env)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            raise RuntimeError(f"保存Cookie失败: {e}")

    @classmethod
    def load_cookies(cls, account_identifier: str, env: str = None) -> Optional[Dict[str, Any]]:
        filename = cls._get_cookie_filename(account_identifier, env)

        if not os.path.exists(filename):
            return None

        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"加载Cookie失败: {e}")

    @classmethod
    def delete_cookies(cls, account_identifier: str, env: str = None) -> bool:
        filename = cls._get_cookie_filename(account_identifier, env)

        if os.path.exists(filename):
            try:
                os.remove(filename)
                return True
            except Exception as e:
                raise RuntimeError(f"删除Cookie文件失败: {e}")
        return False

    @classmethod
    def is_cookie_valid(cls, cookie_data: Dict[str, Any], max_age_hours: int = 24) -> bool:
        if "timestamp" not in cookie_data or "cookies" not in cookie_data:
            return False

        try:
            timestamp = datetime.fromisoformat(cookie_data["timestamp"])
            if datetime.now() - timestamp > timedelta(hours=max_age_hours):
                return False
            if not cookie_data["cookies"] or len(cookie_data["cookies"]) == 0:
                return False
            return True
        except Exception as e:
            raise RuntimeError(f"验证Cookie有效性失败: {e}")

    @classmethod
    def set_cookies_to_context(cls, context: BrowserContext, cookie_data: Dict[str, Any], base_url: str = None) -> None:
        if base_url is None:
            base_url = config.current_env.base_url

        try:
            from urllib.parse import urlparse

            parsed_url = urlparse(base_url)
            domain = parsed_url.netloc
        except Exception as e:
            raise RuntimeError(f"解析基础URL失败: {e}")

        processed_cookies = []
        for cookie in cookie_data["cookies"]:
            new_cookie = cookie.copy()
            if "domain" not in new_cookie or not new_cookie["domain"]:
                new_cookie["domain"] = domain
            if "path" not in new_cookie or not new_cookie["path"]:
                new_cookie["path"] = "/"
            if "name" not in new_cookie or "value" not in new_cookie:
                continue

            if "expires" in new_cookie:
                try:
                    if isinstance(new_cookie["expires"], str):
                        dt = datetime.fromisoformat(new_cookie["expires"].replace("Z", "+00:00"))
                        new_cookie["expires"] = int(dt.timestamp())
                    elif isinstance(new_cookie["expires"], float):
                        new_cookie["expires"] = int(new_cookie["expires"])
                except Exception:
                    del new_cookie["expires"]

            for key in list(new_cookie.keys()):
                if key not in ["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]:
                    del new_cookie[key]

            processed_cookies.append(new_cookie)

        if processed_cookies:
            try:
                context.add_cookies(processed_cookies)
            except Exception:
                for cookie in processed_cookies:
                    try:
                        context.add_cookies([cookie])
                    except Exception:
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
            page = BrowserManager.get_default_page()
        context = page.context

        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                context.clear_cookies()
                cls.set_cookies_to_context(context, cookie_data)
                page.reload()
                return page
            except Exception:
                pass

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
            except Exception:
                pass

        login_func(page)
        cls.save_cookies(account_identifier, context, env)
        return page

    @classmethod
    def get_all_cookie_files(cls, env: str = None) -> list:
        if env is None:
            env = config.env.value
        if not cls.COOKIE_DIR.exists():
            return []

        cookie_files = []
        for filename in os.listdir(cls.COOKIE_DIR):
            if filename.startswith(f"cookies_{env}_") and filename.endswith(".json"):
                cookie_files.append(str(cls.COOKIE_DIR / filename))
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
