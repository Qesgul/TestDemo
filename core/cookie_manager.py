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
from config.settings import config, Environment
from core.browser_manager import BrowserManager


class CookieManager:
    """
    Cookie管理器 - 负责Cookie的存储、读取和验证

    每个账号的Cookie会按环境存储在单独的JSON文件中，文件命名格式：
    cookies_{env}_{account_identifier}.json

    存储路径：与当前文件同目录
    """

    # Cookie存储目录（与当前文件同目录）
    COOKIE_DIR = Path(__file__).parent

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
        # 替换非法文件名字符
        sanitized = re.sub(r'[<>:"/\\|?*@]', '_', filename)
        return sanitized

    @classmethod
    def _get_cookie_filename(cls, account_identifier: str, env: str = None) -> str:
        """
        获取Cookie文件的完整路径

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境

        Returns:
            Cookie文件的完整路径
        """
        if env is None:
            env = config.env.value

        # 文件名格式：cookies_{环境}_{账号标识}.json
        safe_account_id = cls._sanitize_filename(account_identifier)
        filename = f"cookies_{env}_{safe_account_id}.json"
        return str(cls.COOKIE_DIR / filename)

    @classmethod
    def save_cookies(cls, account_identifier: str, context: BrowserContext, env: str = None) -> None:
        """
        保存Cookie到本地文件

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            context: Playwright的BrowserContext对象，用于获取当前页面的Cookie
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境
        """
        cookies = context.cookies()
        cookie_data = {
            "account_identifier": account_identifier,
            "env": env or config.env.value,
            "timestamp": datetime.now().isoformat(),
            "cookies": cookies
        }

        filename = cls._get_cookie_filename(account_identifier, env)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            raise RuntimeError(f"保存Cookie失败: {e}")

    @classmethod
    def load_cookies(cls, account_identifier: str, env: str = None) -> Optional[Dict[str, Any]]:
        """
        从本地文件加载Cookie

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境

        Returns:
            Cookie数据字典，如果文件不存在或加载失败返回None
        """
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
        """
        删除指定账号的Cookie文件

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境

        Returns:
            删除是否成功
        """
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
        """
        验证Cookie的有效性

        Args:
            cookie_data: 从文件加载的Cookie数据字典
            max_age_hours: Cookie的最大有效期（小时），默认24小时

        Returns:
            Cookie是否有效
        """
        if "timestamp" not in cookie_data or "cookies" not in cookie_data:
            return False

        try:
            # 检查Cookie是否过期
            timestamp = datetime.fromisoformat(cookie_data["timestamp"])
            if datetime.now() - timestamp > timedelta(hours=max_age_hours):
                return False

            # 检查是否包含必要的Cookie（简单验证）
            if not cookie_data["cookies"] or len(cookie_data["cookies"]) == 0:
                return False

            return True
        except Exception as e:
            raise RuntimeError(f"验证Cookie有效性失败: {e}")

    @classmethod
    def set_cookies_to_context(cls, context: BrowserContext, cookie_data: Dict[str, Any], base_url: str = None) -> None:
        """
        将Cookie设置到Playwright的BrowserContext中

        Args:
            context: Playwright的BrowserContext对象
            cookie_data: 从文件加载的Cookie数据字典
            base_url: 基础URL，用于设置Cookie的domain，默认使用配置中的base_url
        """
        if base_url is None:
            base_url = config.current_env.base_url

        # 提取域名（用于设置Cookie的domain属性）
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(base_url)
            domain = parsed_url.netloc
        except Exception as e:
            raise RuntimeError(f"解析基础URL失败: {e}")

        # 处理Cookie，确保每个Cookie都有正确的domain属性
        processed_cookies = []
        for cookie in cookie_data["cookies"]:
            # 创建新的cookie字典，避免修改原始数据
            new_cookie = cookie.copy()

            # 如果Cookie没有设置domain属性，则自动设置为当前域名
            if "domain" not in new_cookie or not new_cookie["domain"]:
                new_cookie["domain"] = domain

            # 确保Cookie有必要的属性
            if "path" not in new_cookie or not new_cookie["path"]:
                new_cookie["path"] = "/"

            # Playwright要求的必需字段
            if "name" not in new_cookie or "value" not in new_cookie:
                continue  # 跳过无效的Cookie

            # 处理 expires 字段 - Playwright 期望是 Unix 时间戳（秒）
            if "expires" in new_cookie:
                try:
                    # 如果是字符串格式的日期，转换为时间戳
                    if isinstance(new_cookie["expires"], str):
                        from datetime import datetime
                        dt = datetime.fromisoformat(new_cookie["expires"].replace('Z', '+00:00'))
                        new_cookie["expires"] = int(dt.timestamp())
                    # 如果是浮点数，转换为整数
                    elif isinstance(new_cookie["expires"], float):
                        new_cookie["expires"] = int(new_cookie["expires"])
                    # 如果是 -1 表示会话 Cookie，Playwright 支持
                except Exception:
                    # 如果转换失败，移除 expires 字段，作为会话Cookie处理
                    del new_cookie["expires"]

            # 移除 Playwright 不支持的字段
            for key in list(new_cookie.keys()):
                if key not in ["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]:
                    del new_cookie[key]

            processed_cookies.append(new_cookie)

        # 设置Cookie到BrowserContext
        if processed_cookies:
            try:
                context.add_cookies(processed_cookies)
            except Exception as e:
                print(f"设置Cookie时出现警告: {e}")
                # 尝试逐个设置Cookie，即使部分失败也继续
                for cookie in processed_cookies:
                    try:
                        context.add_cookies([cookie])
                    except Exception:
                        continue

    @classmethod
    def login_with_cookie(cls,
                         account_identifier: str,
                         login_func: callable,
                         page: Page = None,
                         env: str = None,
                         max_age_hours: int = 24) -> Page:
        """
        尝试使用Cookie登录，如果Cookie无效则执行正常登录流程

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            login_func: 正常登录流程的回调函数，需要接受Page对象作为参数
            page: Playwright Page对象（可选，如果未提供则获取默认页面）
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境
            max_age_hours: Cookie的最大有效期（小时），默认24小时

        Returns:
            已登录的Page对象
        """
        if page is None:
            page = BrowserManager.get_default_page()
        context = page.context

        # 尝试加载并使用已有的Cookie
        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                # 清除当前页面的Cookie并设置保存的Cookie
                context.clear_cookies()
                cls.set_cookies_to_context(context, cookie_data)

                # 刷新页面以验证登录状态
                page.reload()
                # 这里可以添加验证登录状态的逻辑，例如检查是否存在退出按钮等
                # 如果验证失败，则执行正常登录流程

                return page
            except Exception as e:
                print(f"使用Cookie登录失败: {e}")

        # Cookie无效或使用Cookie登录失败，执行正常登录流程
        login_func(page)

        # 登录成功后保存Cookie
        cls.save_cookies(account_identifier, context, env)

        return page

    @classmethod
    def login_with_cookie_by_context(cls,
                                   account_identifier: str,
                                   login_func: callable,
                                   context: BrowserContext,
                                   env: str = None,
                                   max_age_hours: int = 24) -> Page:
        """
        尝试使用Cookie登录（使用指定的BrowserContext），如果Cookie无效则执行正常登录流程

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            login_func: 正常登录流程的回调函数，需要接受Page对象作为参数
            context: 指定的BrowserContext对象
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境
            max_age_hours: Cookie的最大有效期（小时），默认24小时

        Returns:
            已登录的Page对象
        """
        page = context.new_page()
        page.set_default_timeout(config.current_env.default_timeout_ms)
        page.goto(config.current_env.base_url)

        # 尝试加载并使用已有的Cookie
        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                # 清除当前页面的Cookie并设置保存的Cookie
                context.clear_cookies()
                cls.set_cookies_to_context(context, cookie_data)

                # 刷新页面以验证登录状态
                page.reload()
                # 这里可以添加验证登录状态的逻辑

                return page
            except Exception as e:
                print(f"使用Cookie登录失败: {e}")

        # Cookie无效或使用Cookie登录失败，执行正常登录流程
        login_func(page)

        # 登录成功后保存Cookie
        cls.save_cookies(account_identifier, context, env)

        return page

    @classmethod
    def get_all_cookie_files(cls, env: str = None) -> list:
        """
        获取指定环境的所有Cookie文件

        Args:
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境

        Returns:
            Cookie文件路径列表
        """
        if env is None:
            env = config.env.value

        cookie_files = []
        for filename in os.listdir(cls.COOKIE_DIR):
            if filename.startswith(f"cookies_{env}_") and filename.endswith(".json"):
                cookie_files.append(str(cls.COOKIE_DIR / filename))

        return cookie_files

    @classmethod
    def delete_all_cookies(cls, env: str = None) -> int:
        """
        删除指定环境的所有Cookie文件

        Args:
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境

        Returns:
            删除的Cookie文件数量
        """
        cookie_files = cls.get_all_cookie_files(env)
        count = 0
        for file_path in cookie_files:
            try:
                os.remove(file_path)
                count += 1
            except Exception as e:
                print(f"删除Cookie文件失败 {file_path}: {e}")

        return count

    @classmethod
    def validate_and_use_cookie(cls,
                               account_identifier: str,
                               context: BrowserContext,
                               env: str = None,
                               max_age_hours: int = 24) -> bool:
        """
        验证Cookie有效性并设置到BrowserContext中

        Args:
            account_identifier: 账号标识（如用户名、邮箱等）
            context: Playwright的BrowserContext对象
            env: 环境名称（dev/test/prod），默认使用配置中的当前环境
            max_age_hours: Cookie的最大有效期（小时），默认24小时

        Returns:
            是否成功使用Cookie登录
        """
        cookie_data = cls.load_cookies(account_identifier, env)
        if cookie_data and cls.is_cookie_valid(cookie_data, max_age_hours):
            try:
                cls.set_cookies_to_context(context, cookie_data)
                return True
            except Exception as e:
                print(f"使用Cookie登录失败: {e}")
                return False

        return False
