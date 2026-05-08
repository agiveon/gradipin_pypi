"""Command-line interface: ``gradipin login``, ``list``, ``status``, etc."""
from __future__ import annotations

import sys

import click
import requests

from . import __version__
from .client import USER_AGENT
from .config import (
    CONFIG_FILE,
    clear_key,
    resolve_api_url,
    resolve_key,
    save_key,
)
from .exceptions import GradipinError

_CHECK = "\u2713"
_DASH = "\u2014"
_GREEN_CIRCLE = "\U0001f7e2"
_WHITE_CIRCLE = "\u26aa"


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Gradipin: static URLs for your Gradio demos."""


@main.command()
@click.option("--key", prompt="Paste your Gradipin API key", hide_input=True)
def login(key: str) -> None:
    """Save your API key locally."""
    save_key(key.strip())
    click.echo(f"{_CHECK} Key saved to {CONFIG_FILE}")


@main.command()
def logout() -> None:
    """Remove the saved API key."""
    clear_key()
    click.echo(f"{_CHECK} Logged out.")


@main.command(name="list")
def list_apps() -> None:
    """List your apps and their current status."""
    try:
        key = resolve_key()
    except GradipinError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    r = requests.get(
        f"{resolve_api_url()}/apps",
        headers={
            "Authorization": f"Bearer {key}",
            "User-Agent": USER_AGENT,
        },
        timeout=10,
    )
    r.raise_for_status()
    apps = r.json().get("apps", [])
    if not apps:
        click.echo("No apps yet. Create one at https://gradipin.com/dashboard")
        return
    for app in apps:
        status_icon = _GREEN_CIRCLE if app.get("status") == "live" else _WHITE_CIRCLE
        url = app.get("current_url", _DASH)
        slug = app["slug"]
        click.echo(f"{status_icon} {slug:<30} {url}")


@main.command()
@click.argument("app")
def status(app: str) -> None:
    """Check the live status of an app."""
    from .client import status as get_status

    try:
        result = get_status(app)
        current_url = result.get("current_url", _DASH)
        last_seen = result.get("last_seen", _DASH)
        click.echo(f"App: {app}")
        click.echo(f"Status: {result.get('status', 'unknown')}")
        click.echo(f"Current URL: {current_url}")
        click.echo(f"Last seen: {last_seen}")
    except GradipinError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
