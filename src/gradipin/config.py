"""Configuration resolution: args > env > config file > .env file."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import dotenv_values

from .exceptions import ConfigurationError

DEFAULT_API_URL: Final = "https://api.gradipin.com/v1"
DEFAULT_HEARTBEAT_SECONDS: Final = 30
CONFIG_DIR: Final = Path.home() / ".gradipin"
CONFIG_FILE: Final = CONFIG_DIR / "config"


def resolve_key(explicit: str | None = None) -> str:
    """Find the API key from args, env, config file, or .env."""
    if explicit:
        return explicit

    env_key = os.environ.get("GRADIPIN_KEY")
    if env_key:
        return env_key

    if CONFIG_FILE.exists():
        try:
            stored = CONFIG_FILE.read_text().strip()
            if stored:
                return stored
        except OSError:
            pass

    dotenv_path = Path.cwd() / ".env"
    if dotenv_path.exists():
        values = dotenv_values(dotenv_path)
        dotenv_key = values.get("GRADIPIN_KEY")
        if dotenv_key:
            return dotenv_key

    raise ConfigurationError(
        "No Gradipin API key found. Set GRADIPIN_KEY environment variable, "
        "run `gradipin login`, or pass key=... explicitly."
    )


def resolve_api_url() -> str:
    """Return the Gradipin API base URL, honoring the GRADIPIN_API_URL override."""
    return os.environ.get("GRADIPIN_API_URL", DEFAULT_API_URL)


def resolve_heartbeat_seconds(explicit: int | None = None) -> int:
    """Return the heartbeat interval, in seconds."""
    if explicit is not None:
        return explicit
    env = os.environ.get("GRADIPIN_HEARTBEAT")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    return DEFAULT_HEARTBEAT_SECONDS


def save_key(key: str) -> None:
    """Write the API key to the user's config file with restrictive permissions."""
    CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)
    CONFIG_FILE.write_text(key)
    CONFIG_FILE.chmod(0o600)


def clear_key() -> None:
    """Remove the saved API key, if any."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
