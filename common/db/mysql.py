# -*- coding: utf-8 -*-
"""MySQL 薄客户端：仅负责连接开关，cursor / SQL / commit 由调用方掌控。"""
from contextlib import contextmanager

import pymysql

from common.db.config import mysql_connect_kwargs


class MySQLClient:
    def __init__(self, **overrides):
        """构造薄客户端，保存连接参数。不会立即开连接（懒连接）。

        Args:
            **overrides: 可覆盖 settings.yaml 中的任意连接参数（如 database='test_db'）。
        """
        self._kwargs = {**mysql_connect_kwargs(), **overrides}

    def get_connection(self):
        """开一个新连接，调用方负责 close。

        适合需要细粒度控制连接生命周期的场景。多数场景推荐用 connection() 上下文管理器。
        """
        return pymysql.connect(**self._kwargs)

    @contextmanager
    def connection(self, *, commit: bool = False):
        """上下文管理器：自动 close；commit=True 时成功提交 / 异常回滚。

        Args:
            commit: 是否在 with 块正常退出时提交事务（默认 False）。
                    ⚠ 操作生产 RDS 时请显式传 commit=True，以防误写默认不落库。

        用法：
            # 查询
            with mysql_db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT radio FROM user_group_common WHERE group_name=%s", ["xx"])
                    rows = cur.fetchall()

            # 写入（必须显式 commit=True）
            with mysql_db.connection(commit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE user_group_common SET radio=%s WHERE group_name=%s", [r, g])
        """
        conn = self.get_connection()
        try:
            yield conn
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
