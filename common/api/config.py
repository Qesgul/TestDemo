# -*- coding: utf-8 -*-
"""桥接层：从 config.settings 读取 api 配置，供 ApiClient 使用。"""
from urllib.parse import urlsplit

from config.settings import get_config


def api_base_url() -> str:
    """返回 API base URL；settings.yaml 中为空时回退当前环境 base_url 的 origin。"""
    cfg = get_config()
    if cfg.api.base_url:
        return cfg.api.base_url.rstrip("/")
    parts = urlsplit(cfg.current_env.base_url)
    return f"{parts.scheme}://{parts.netloc}"


def api_default_headers() -> dict:
    """返回配置的默认请求头（副本）。"""
    return dict(get_config().api.default_headers)


def api_timeout_ms() -> int:
    """返回 API 请求超时（毫秒）。"""
    return get_config().api.timeout_ms
