# -*- coding: utf-8 -*-
"""桥接层：从 config.settings 读取配置，翻译成 pymysql / redis 连接参数。"""
import pymysql

from config.settings import get_config


def mysql_connect_kwargs(*, dict_cursor: bool = True) -> dict:
    """返回 pymysql.connect 所需的关键字参数。

    Args:
        dict_cursor: 是否使用 DictCursor（默认 True，查询结果为 dict 列表）。
                     传 False 可得普通 tuple cursor。
    """
    db = get_config().database
    kwargs = dict(
        host=db.host,
        port=db.port,
        user=db.user,
        password=db.password,
        database=db.database,
        charset=db.charset,
        connect_timeout=db.connect_timeout,
    )
    if dict_cursor:
        kwargs["cursorclass"] = pymysql.cursors.DictCursor
    return kwargs


def redis_connect_kwargs() -> dict:
    """返回 redis.Redis 所需的关键字参数。"""
    r = get_config().redis
    return dict(host=r.host, port=r.port, password=r.password, db=r.db)
