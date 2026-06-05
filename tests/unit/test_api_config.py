# -*- coding: utf-8 -*-
def test_api_config_env_override(monkeypatch):
    from config.settings import ApiConfig
    monkeypatch.setenv("TEST_API_BASE_URL", "https://api.example.com")
    cfg = ApiConfig({"base_url": "https://yaml.example.com", "timeout_ms": 9000})
    assert cfg.base_url == "https://api.example.com"   # 环境变量优先
    assert cfg.timeout_ms == 9000


def test_api_config_default_headers_and_fallback():
    from config.settings import ApiConfig
    cfg = ApiConfig({"default_headers": {"Accept": "application/json"}})
    assert cfg.default_headers["Accept"] == "application/json"
    assert cfg.base_url == ""          # 留空，回退逻辑在桥接层
    assert cfg.timeout_ms == 15000     # 默认值
