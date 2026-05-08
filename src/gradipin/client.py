"""Public API: ``gradipin.share()``, ``gradipin.session()``, ``gradipin.status()``."""
from __future__ import annotations

import atexit
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import requests

from .config import (
    resolve_api_url,
    resolve_heartbeat_seconds,
    resolve_key,
)
from .exceptions import (
    APIError,
    AppNotFoundError,
    AuthenticationError,
)
from .heartbeat import HeartbeatThread

logger = logging.getLogger("gradipin")

USER_AGENT = "gradipin-python/0.1.1"


def _public_host(api_url: str) -> str:
    """Strip the ``/api/v1`` or ``/v1`` suffix from an API URL.

    Used to derive the public-facing host (for ``/go/<app>`` and ``/dashboard``
    URLs) when the server doesn't tell us what they are. Best-effort guess only:
    the canonical URL should always come from the API response when available.
    """
    return api_url.removesuffix("/api/v1").removesuffix("/v1")


class _Session:
    """Owns the connection to the Gradipin backend for one running app."""

    def __init__(
        self,
        key: str,
        app: str,
        url: str,
        api_url: str,
        heartbeat_seconds: int,
        offline_message: str | None = None,
    ) -> None:
        self.key = key
        self.app = app
        self.url = url
        self.api_url = api_url
        self.offline_message = offline_message
        self.public_url: str = self._fallback_public_url()
        self._heartbeat = HeartbeatThread(self._tick, heartbeat_seconds)
        self._http = requests.Session()
        self._http.headers["Authorization"] = f"Bearer {key}"
        self._http.headers["User-Agent"] = USER_AGENT
        self._closed = False

    def _fallback_public_url(self) -> str:
        """Best-effort guess at the public URL when the API doesn't supply one."""
        return f"{_public_host(self.api_url)}/go/{self.app}"

    def _absorb_share_url(self, response: dict[str, Any]) -> None:
        """Update ``self.public_url`` if the server returned a fresh canonical URL."""
        server_url = response.get("share_url")
        if isinstance(server_url, str) and server_url and server_url != self.public_url:
            logger.debug(
                "Gradipin share URL updated: %s -> %s", self.public_url, server_url
            )
            self.public_url = server_url

    def start(self) -> None:
        response = self._post(
            "/update-target",
            {
                "app": self.app,
                "url": self.url,
                "offline_message": self.offline_message,
            },
        )
        self._absorb_share_url(response)
        self._heartbeat.start()
        atexit.register(self.close)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._heartbeat.stop()
        if self._heartbeat.is_alive():
            self._heartbeat.join(timeout=5.0)
        try:
            self._post("/offline", {"app": self.app})
        except Exception:
            logger.debug("Failed to mark app offline on shutdown", exc_info=True)

    def _tick(self) -> None:
        response = self._post("/heartbeat", {"app": self.app, "url": self.url})
        self._absorb_share_url(response)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            r = self._http.post(f"{self.api_url}{path}", json=payload, timeout=10)
        except requests.RequestException as e:
            raise APIError(f"Network error contacting Gradipin: {e}") from e

        if r.status_code == 401:
            raise AuthenticationError("Invalid or revoked API key.")
        if r.status_code == 404:
            raise AppNotFoundError(
                f"App '{self.app}' not found on this account. "
                f"Create it at {_public_host(self.api_url)}/dashboard."
            )
        if r.status_code >= 400:
            raise APIError(
                f"Gradipin API returned {r.status_code}: {r.text}",
                status_code=r.status_code,
            )
        try:
            data = r.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}


def share(
    demo: Any,
    app: str,
    *,
    key: str | None = None,
    heartbeat_seconds: int | None = None,
    offline_message: str | None = None,
    block: bool = True,
) -> _Session:
    """Launch a Gradio demo and route a Gradipin URL to it.

    Args:
        demo: A Gradio Blocks/Interface object.
        app: The slug of the app on your Gradipin account (e.g. ``vision-model``).
        key: API key. Falls back to ``GRADIPIN_KEY`` env var or saved config.
        heartbeat_seconds: How often to ping the backend. Default 30.
        offline_message: Custom message shown when the demo isn't running.
        block: If True (default), blocks until the demo is stopped.

    Returns:
        The active session. If ``block=False``, call ``session.close()`` when done.
    """
    try:
        from gradio import Blocks
    except ImportError as e:
        raise ImportError(
            "Gradio is required for gradipin.share(). "
            "Install with: pip install gradipin[gradio]"
        ) from e

    if not isinstance(demo, Blocks):
        raise TypeError(
            f"Expected a Gradio Blocks/Interface, got {type(demo).__name__}"
        )

    resolved_key = resolve_key(key)
    api_url = resolve_api_url()
    interval = resolve_heartbeat_seconds(heartbeat_seconds)

    _, _, share_url = demo.launch(
        share=True,
        prevent_thread_lock=True,
        quiet=True,
    )
    if not share_url:
        raise RuntimeError(
            "Gradio did not return a public share URL. "
            "Make sure your network allows share=True tunnels."
        )

    s = _Session(
        key=resolved_key,
        app=app,
        url=share_url,
        api_url=api_url,
        heartbeat_seconds=interval,
        offline_message=offline_message,
    )
    s.start()

    arrow = "\u2192"
    print(
        f"\n  Gradipin: {s.public_url} "
        f"{arrow} {share_url}\n  Heartbeat every {interval}s. Ctrl+C to stop.\n",
        file=sys.stderr,
    )

    if block:
        try:
            demo.block_thread()
        except KeyboardInterrupt:
            pass
        finally:
            s.close()

    return s


@contextmanager
def session(
    app: str,
    url: str,
    *,
    key: str | None = None,
    heartbeat_seconds: int | None = None,
    offline_message: str | None = None,
) -> Iterator[_Session]:
    """Lower-level context manager for non-Gradio frameworks.

    Use when you have your own public URL (ngrok, cloudflared, etc.) and just
    want Gradipin to manage the redirect to it::

        with gradipin.session("my-api", url="https://abc.ngrok.io"):
            run_my_fastapi_server()
    """
    resolved_key = resolve_key(key)
    api_url = resolve_api_url()
    interval = resolve_heartbeat_seconds(heartbeat_seconds)

    s = _Session(
        key=resolved_key,
        app=app,
        url=url,
        api_url=api_url,
        heartbeat_seconds=interval,
        offline_message=offline_message,
    )
    s.start()
    try:
        yield s
    finally:
        s.close()


def status(app: str, *, key: str | None = None) -> dict[str, Any]:
    """Check whether an app is currently live."""
    resolved_key = resolve_key(key)
    api_url = resolve_api_url()
    r = requests.get(
        f"{api_url}/apps/{app}/status",
        headers={
            "Authorization": f"Bearer {resolved_key}",
            "User-Agent": USER_AGENT,
        },
        timeout=10,
    )
    if r.status_code == 401:
        raise AuthenticationError("Invalid or revoked API key.")
    if r.status_code == 404:
        raise AppNotFoundError(f"App '{app}' not found.")
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {}
