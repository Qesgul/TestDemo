# -*- coding: utf-8 -*-
"""Redis 薄客户端：仅负责连接开关，命令由调用方掌控。

文件命名为 redis_client.py（而非 redis.py），避免与三方库 `redis` 包重名导致
循环 import。
"""
from contextlib import contextmanager

import redis

from common.db.config import redis_connect_kwargs


class RedisClient:
    def __init__(self, **overrides):
        """构造薄客户端，保存连接参数。不会立即开连接（懒连接）。

        Args:
            **overrides: 可覆盖 settings.yaml 中的任意连接参数（如 db=1）。
        """
        self._kwargs = {**redis_connect_kwargs(), **overrides}

    def get_client(self):
        """返回一个 redis.Redis 客户端，调用方负责 close。

        适合需要细粒度控制的场景。多数场景推荐用 client() 上下文管理器。
        """
        return redis.Redis(**self._kwargs)

    @contextmanager
    def client(self):
        """上下文管理器：用完自动 close。

        用法：
            with redis_db.client() as r:
                r.delete("znzmo:group:all")
                r.set("key", "value", ex=60)
        """
        r = self.get_client()
        try:
            yield r
        finally:
            r.close()
