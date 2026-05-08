"""Tests for gradipin.client."""
from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
import responses

import gradipin
from gradipin.client import _public_host, _Session
from gradipin.exceptions import (
    APIError,
    AppNotFoundError,
    AuthenticationError,
)

API = "http://test.gradipin.local/v1"


@pytest.fixture(autouse=True)
def _api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADIPIN_API_URL", API)
    monkeypatch.setenv("GRADIPIN_KEY", "test-key")


@pytest.fixture
def mock_api() -> Iterator[responses.RequestsMock]:
    """Active `responses` mock with permissive heartbeat/offline endpoints pre-registered.

    Heartbeat fires immediately when a session starts; we don't want that ambient
    background traffic to fail tests that aren't specifically about heartbeats.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST, f"{API}/heartbeat", json={}, status=200)
        rsps.add(responses.POST, f"{API}/offline", json={}, status=200)
        yield rsps


def _make_session(**overrides: object) -> _Session:
    kwargs: dict[str, object] = {
        "key": "test-key",
        "app": "demo",
        "url": "https://abc.example",
        "api_url": API,
        "heartbeat_seconds": 60,
        "offline_message": None,
    }
    kwargs.update(overrides)
    return _Session(**kwargs)  # type: ignore[arg-type]


def test_session_start_posts_update_target(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)

    s = _make_session()
    try:
        s.start()
    finally:
        s.close()

    update_calls = [c for c in mock_api.calls if c.request.url == f"{API}/update-target"]
    assert len(update_calls) == 1
    assert update_calls[0].request.headers["Authorization"] == "Bearer test-key"
    body = update_calls[0].request.body
    assert isinstance(body, (bytes, str))
    body_bytes = body.encode() if isinstance(body, str) else body
    assert b'"app": "demo"' in body_bytes
    assert b'"url": "https://abc.example"' in body_bytes


def test_session_close_marks_offline(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)

    s = _make_session()
    s.start()
    s.close()

    paths = [c.request.url for c in mock_api.calls]
    assert f"{API}/update-target" in paths
    assert f"{API}/offline" in paths


def test_session_close_is_idempotent(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)

    s = _make_session()
    s.start()
    s.close()
    s.close()

    offline_calls = [c for c in mock_api.calls if c.request.url.endswith("/offline")]
    assert len(offline_calls) == 1


def test_401_raises_authentication_error(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={"error": "bad key"}, status=401)
    s = _make_session()
    with pytest.raises(AuthenticationError):
        s.start()


def test_404_raises_app_not_found_error(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={"error": "no such app"}, status=404)
    s = _make_session()
    with pytest.raises(AppNotFoundError):
        s.start()


def test_5xx_raises_api_error_with_status_code(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", body="boom", status=500)
    s = _make_session()
    with pytest.raises(APIError) as exc_info:
        s.start()
    assert exc_info.value.status_code == 500


def test_network_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def boom(*_args: object, **_kwargs: object) -> None:
        raise requests.ConnectionError("dns failure")

    s = _make_session()
    monkeypatch.setattr(s._http, "post", boom)
    with pytest.raises(APIError, match="Network error"):
        s.start()


def test_offline_message_is_forwarded(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)
    s = _make_session(offline_message="brb, deploying")
    try:
        s.start()
    finally:
        s.close()

    update_calls = [c for c in mock_api.calls if c.request.url.endswith("/update-target")]
    body = update_calls[0].request.body
    body_bytes = body.encode() if isinstance(body, str) else body
    assert b"brb, deploying" in body_bytes


def test_heartbeat_actually_pings(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)

    s = _make_session(heartbeat_seconds=0)
    s.start()
    try:
        time.sleep(0.2)
    finally:
        s.close()

    heartbeat_calls = [c for c in mock_api.calls if c.request.url.endswith("/heartbeat")]
    assert len(heartbeat_calls) >= 1


def test_offline_failure_during_close_is_swallowed(
    mock_api: responses.RequestsMock,
) -> None:
    mock_api.reset()
    mock_api.add(responses.POST, f"{API}/heartbeat", json={}, status=200)
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)
    mock_api.add(responses.POST, f"{API}/offline", body="server gone", status=503)

    s = _make_session()
    s.start()
    s.close()


def test_status_returns_dict(mock_api: responses.RequestsMock) -> None:
    mock_api.add(
        responses.GET,
        f"{API}/apps/demo/status",
        json={"status": "live", "current_url": "https://abc"},
        status=200,
    )
    result = gradipin.status("demo")
    assert result["status"] == "live"
    assert result["current_url"] == "https://abc"


def test_status_401_raises(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.GET, f"{API}/apps/demo/status", json={}, status=401)
    with pytest.raises(AuthenticationError):
        gradipin.status("demo")


def test_status_404_raises(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.GET, f"{API}/apps/demo/status", json={}, status=404)
    with pytest.raises(AppNotFoundError):
        gradipin.status("demo")


def test_session_context_manager_starts_and_stops(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)

    with gradipin.session("demo", url="https://x.example") as s:
        assert s.app == "demo"
        assert s.url == "https://x.example"

    paths = [c.request.url for c in mock_api.calls]
    assert f"{API}/update-target" in paths
    assert f"{API}/offline" in paths


def test_session_context_manager_closes_on_exception(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=200)

    with (
        pytest.raises(RuntimeError, match="user code"),
        gradipin.session("demo", url="https://x.example"),
    ):
        raise RuntimeError("user code")

    assert any(c.request.url.endswith("/offline") for c in mock_api.calls)


def test_share_without_gradio_raises_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import sys

    monkeypatch.delitem(sys.modules, "gradio", raising=False)

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "gradio" or name.startswith("gradio."):
            raise ImportError("no gradio")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="Gradio is required"):
        gradipin.share(object(), app="demo")


def test_share_rejects_non_blocks_object() -> None:
    pytest.importorskip("gradio")
    with pytest.raises(TypeError, match="Expected a Gradio Blocks"):
        gradipin.share("not a Blocks object", app="demo")


# ---------------------------------------------------------------------------
# public_url / share_url tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("api_url", "expected"),
    [
        ("http://test.gradipin.local/v1", "http://test.gradipin.local"),
        ("https://gradipin.lovable.app/api/v1", "https://gradipin.lovable.app"),
        ("https://no-suffix.example.com", "https://no-suffix.example.com"),
        ("https://only-v1.example.com/v1", "https://only-v1.example.com"),
    ],
)
def test_public_host_strips_known_api_suffixes(api_url: str, expected: str) -> None:
    assert _public_host(api_url) == expected


def test_session_init_seeds_public_url_from_fallback() -> None:
    s = _make_session()
    assert s.public_url == "http://test.gradipin.local/go/demo"


def test_start_captures_share_url_from_response(mock_api: responses.RequestsMock) -> None:
    canonical = "https://gradipin.lovable.app/go/amir/ocr-pii"
    mock_api.add(
        responses.POST,
        f"{API}/update-target",
        json={"ok": True, "share_url": canonical, "live": True},
        status=200,
    )

    s = _make_session()
    try:
        s.start()
        assert s.public_url == canonical
    finally:
        s.close()


def test_start_falls_back_when_share_url_missing(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={"ok": True}, status=200)

    s = _make_session()
    try:
        s.start()
        assert s.public_url == "http://test.gradipin.local/go/demo"
    finally:
        s.close()


def test_start_ignores_non_string_share_url(mock_api: responses.RequestsMock) -> None:
    mock_api.add(
        responses.POST,
        f"{API}/update-target",
        json={"share_url": None},
        status=200,
    )
    s = _make_session()
    try:
        s.start()
        assert s.public_url == "http://test.gradipin.local/go/demo"
    finally:
        s.close()


@responses.activate
def test_heartbeat_updates_public_url_when_server_returns_new_one() -> None:
    initial = "https://gradipin.lovable.app/go/amir/demo"
    updated = "https://custom-domain.example.com/go/amir/demo"
    responses.post(f"{API}/update-target", json={"share_url": initial}, status=200)
    responses.post(f"{API}/heartbeat", json={"share_url": updated}, status=200)
    responses.post(f"{API}/offline", json={}, status=200)

    s = _make_session(heartbeat_seconds=0)
    s.start()
    assert s.public_url == initial
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline and s.public_url != updated:
            time.sleep(0.02)
    finally:
        s.close()
    assert s.public_url == updated


def test_404_dashboard_url_is_derived_from_api_url(mock_api: responses.RequestsMock) -> None:
    mock_api.add(responses.POST, f"{API}/update-target", json={}, status=404)

    s = _make_session()
    with pytest.raises(AppNotFoundError) as exc_info:
        s.start()

    msg = str(exc_info.value)
    assert "http://test.gradipin.local/dashboard" in msg
    assert "gradipin.com" not in msg
