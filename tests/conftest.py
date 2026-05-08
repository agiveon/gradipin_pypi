"""Shared test fixtures."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from gradipin import config


@pytest.fixture(autouse=True)
def isolated_config_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Redirect config + cwd + env so tests never touch the user's real ~/.gradipin."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_cwd = tmp_path / "cwd"
    fake_cwd.mkdir()

    fake_config_dir = fake_home / ".gradipin"
    fake_config_file = fake_config_dir / "config"

    monkeypatch.setattr(config, "CONFIG_DIR", fake_config_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", fake_config_file)
    monkeypatch.chdir(fake_cwd)

    for var in ("GRADIPIN_KEY", "GRADIPIN_API_URL", "GRADIPIN_HEARTBEAT"):
        monkeypatch.delenv(var, raising=False)

    yield fake_cwd
