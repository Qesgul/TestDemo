# -*- coding: utf-8 -*-
"""common/db 数据库支持能力单测（mock 连接，不依赖真实库）。"""
import pytest


# ── Task 1: 配置类 ─────────────────────────────────────────────
def test_database_config_env_override(monkeypatch):
    from config.settings import DatabaseConfig
    monkeypatch.setenv("TEST_DB_PASSWORD", "override_pwd")
    monkeypatch.setenv("TEST_DB_HOST", "env_host")
    cfg = DatabaseConfig({"host": "yaml_host", "user": "u",
                          "password": "yaml_pwd", "db": "d"})
    assert cfg.password == "override_pwd"   # 环境变量优先
    assert cfg.host == "env_host"
    assert cfg.user == "u"                  # 未设环境变量则回退 yaml
    assert cfg.database == "d"
    assert cfg.charset == "utf8mb4"         # 默认值


def test_redis_config_blank_password_is_none():
    from config.settings import RedisConfig
    cfg = RedisConfig({"host": "h", "port": 6379, "password": "", "db": 0})
    assert cfg.password is None             # 空串归一为 None
    assert cfg.port == 6379


# ── Task 2: 桥接层 ─────────────────────────────────────────────
def test_mysql_connect_kwargs_has_dictcursor():
    import pymysql
    from common.db.config import mysql_connect_kwargs
    kw = mysql_connect_kwargs()
    assert kw["cursorclass"] is pymysql.cursors.DictCursor
    assert "host" in kw and "database" in kw and "connect_timeout" in kw


def test_mysql_connect_kwargs_no_dictcursor_opt_out():
    from common.db.config import mysql_connect_kwargs
    kw = mysql_connect_kwargs(dict_cursor=False)
    assert "cursorclass" not in kw


def test_redis_connect_kwargs_shape():
    from common.db.config import redis_connect_kwargs
    kw = redis_connect_kwargs()
    assert set(kw) == {"host", "port", "password", "db"}


# ── Task 3: MySQLClient ────────────────────────────────────────
def test_mysql_client_lazy_no_connect_on_init(monkeypatch):
    import common.db.mysql as m
    called = {"n": 0}
    monkeypatch.setattr(m.pymysql, "connect",
                        lambda **kw: called.__setitem__("n", called["n"] + 1))
    m.MySQLClient()                     # 构造不应触发连接
    assert called["n"] == 0


def test_mysql_connection_commit_and_close(monkeypatch):
    import common.db.mysql as m

    class FakeConn:
        def __init__(self): self.committed = False; self.closed = False; self.rolled = False
        def commit(self): self.committed = True
        def rollback(self): self.rolled = True
        def close(self): self.closed = True

    fake = FakeConn()
    monkeypatch.setattr(m.pymysql, "connect", lambda **kw: fake)
    client = m.MySQLClient()
    with client.connection(commit=True) as conn:
        assert conn is fake
    assert fake.committed is True and fake.closed is True


def test_mysql_connection_rollback_on_exception(monkeypatch):
    import common.db.mysql as m

    class FakeConn:
        def __init__(self): self.committed = False; self.closed = False; self.rolled = False
        def commit(self): self.committed = True
        def rollback(self): self.rolled = True
        def close(self): self.closed = True

    fake = FakeConn()
    monkeypatch.setattr(m.pymysql, "connect", lambda **kw: fake)
    client = m.MySQLClient()
    with pytest.raises(ValueError):
        with client.connection(commit=True) as conn:
            raise ValueError("boom")
    assert fake.rolled is True and fake.closed is True and fake.committed is False


# ── Task 4: RedisClient ────────────────────────────────────────
def test_redis_client_context_closes(monkeypatch):
    import common.db.redis_client as rc

    class FakeRedis:
        def __init__(self): self.closed = False
        def close(self): self.closed = True

    fake = FakeRedis()
    monkeypatch.setattr(rc.redis, "Redis", lambda **kw: fake)
    client = rc.RedisClient()
    with client.client() as r:
        assert r is fake
    assert fake.closed is True


# ── Task 5: 导出 + fixtures + live 烟雾测试 ─────────────────────
def test_db_package_exports():
    from common.db import MySQLClient, RedisClient
    assert MySQLClient is not None and RedisClient is not None


def test_db_fixtures_return_clients(mysql_db, redis_db):
    from common.db import MySQLClient, RedisClient
    assert isinstance(mysql_db, MySQLClient)
    assert isinstance(redis_db, RedisClient)


@pytest.mark.skip(reason="live: 连真实生产 RDS，手动按需运行（去掉本 skip 即可验证连通性）")
def test_live_mysql_smoke(mysql_db):
    with mysql_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            assert cur.fetchone()["ok"] == 1
