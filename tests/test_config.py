"""Tests for gradipin.config."""
from __future__ import annotations

from pathlib import Path

import pytest

from gradipin import config
from gradipin.exceptions import ConfigurationError


def test_explicit_key_wins_over_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADIPIN_KEY", "from-env")
    assert config.resolve_key("explicit") == "explicit"


def test_env_key_wins_over_config_file() -> None:
    config.save_key("from-file")
    import os

    os.environ["GRADIPIN_KEY"] = "from-env"
    try:
        assert config.resolve_key() == "from-env"
    finally:
        del os.environ["GRADIPIN_KEY"]


def test_config_file_wins_over_dotenv(isolated_config_dir: Path) -> None:
    config.save_key("from-config-file")
    (isolated_config_dir / ".env").write_text("GRADIPIN_KEY=from-dotenv\n")
    assert config.resolve_key() == "from-config-file"


def test_dotenv_used_when_nothing_else_set(isolated_config_dir: Path) -> None:
    (isolated_config_dir / ".env").write_text("GRADIPIN_KEY=from-dotenv\n")
    assert config.resolve_key() == "from-dotenv"


def test_missing_key_raises() -> None:
    with pytest.raises(ConfigurationError):
        config.resolve_key()


def test_save_and_clear_key_roundtrip() -> None:
    config.save_key("abc123")
    assert config.CONFIG_FILE.read_text() == "abc123"
    assert config.resolve_key() == "abc123"

    config.clear_key()
    assert not config.CONFIG_FILE.exists()
    with pytest.raises(ConfigurationError):
        config.resolve_key()


def test_save_key_sets_restrictive_permissions() -> None:
    config.save_key("secret")
    mode = config.CONFIG_FILE.stat().st_mode & 0o777
    assert mode == 0o600


def test_resolve_api_url_default() -> None:
    assert config.resolve_api_url() == config.DEFAULT_API_URL


def test_resolve_api_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADIPIN_API_URL", "http://localhost:1234/v1")
    assert config.resolve_api_url() == "http://localhost:1234/v1"


def test_resolve_heartbeat_explicit_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADIPIN_HEARTBEAT", "5")
    assert config.resolve_heartbeat_seconds(60) == 60


def test_resolve_heartbeat_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADIPIN_HEARTBEAT", "10")
    assert config.resolve_heartbeat_seconds() == 10


def test_resolve_heartbeat_default() -> None:
    assert config.resolve_heartbeat_seconds() == config.DEFAULT_HEARTBEAT_SECONDS


def test_resolve_heartbeat_invalid_env_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADIPIN_HEARTBEAT", "not-an-int")
    assert config.resolve_heartbeat_seconds() == config.DEFAULT_HEARTBEAT_SECONDS


def test_clear_key_when_no_key_is_a_noop() -> None:
    assert not config.CONFIG_FILE.exists()
    config.clear_key()
    assert not config.CONFIG_FILE.exists()
