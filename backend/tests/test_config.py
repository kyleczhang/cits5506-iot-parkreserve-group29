"""Configuration-loading tests for environment and dotenv precedence."""

from __future__ import annotations

import os

import app.config as config_module


def test_load_settings_reads_dotenv_when_env_missing(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("MQTT_HOST=broker.test\nMQTT_PORT=2883\nMQTT_TLS=true\n", encoding="utf-8")

    monkeypatch.setattr(config_module, "_DOTENV_PATH", dotenv)
    for key in ("MQTT_HOST", "MQTT_PORT", "MQTT_TLS"):
        monkeypatch.delenv(key, raising=False)
    config_module.load_local_env.cache_clear()

    settings = config_module.load_settings()

    assert settings.mqtt_host == "broker.test"
    assert settings.mqtt_port == 2883
    assert settings.mqtt_tls is True

    for key in ("MQTT_HOST", "MQTT_PORT", "MQTT_TLS"):
        os.environ.pop(key, None)
    config_module.load_local_env.cache_clear()


def test_load_settings_prefers_real_env_over_dotenv(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("MQTT_HOST=broker.test\nMQTT_PORT=2883\nMQTT_TLS=false\n", encoding="utf-8")

    monkeypatch.setattr(config_module, "_DOTENV_PATH", dotenv)
    monkeypatch.setenv("MQTT_HOST", "exported.test")
    monkeypatch.setenv("MQTT_PORT", "3883")
    monkeypatch.setenv("MQTT_TLS", "true")
    config_module.load_local_env.cache_clear()

    settings = config_module.load_settings()

    assert settings.mqtt_host == "exported.test"
    assert settings.mqtt_port == 3883
    assert settings.mqtt_tls is True

    for key in ("MQTT_HOST", "MQTT_PORT", "MQTT_TLS"):
        os.environ.pop(key, None)
    config_module.load_local_env.cache_clear()
