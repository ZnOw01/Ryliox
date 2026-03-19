from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from plugins.auth import AuthPlugin

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload=None,
        json_error: Exception | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error
        self.text = text

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakeHttp:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def _make_plugin(response: _FakeResponse) -> tuple[AuthPlugin, _FakeHttp]:
    http = _FakeHttp(response)
    plugin = AuthPlugin()
    plugin.kernel = SimpleNamespace(http=http)
    return plugin, http


def test_get_status_marks_expired_session_from_structured_json():
    plugin, http = _make_plugin(
        _FakeResponse(200, {"user_type": "Expired", "profile": {"name": "demo"}})
    )

    status = asyncio.run(plugin.get_status())

    assert http.calls == [("/profile/", {"allow_redirects": False})]
    assert status == {"valid": False, "reason": "subscription_expired"}


def test_get_status_accepts_authenticated_html_profile_response():
    plugin, _ = _make_plugin(
        _FakeResponse(
            200,
            json_error=ValueError("bad json"),
            text="<html><body><a href='/logout'>Sign out</a></body></html>",
        )
    )

    status = asyncio.run(plugin.get_status())

    assert status == {"valid": True, "reason": None}


def test_get_status_treats_non_json_login_html_as_invalid():
    plugin, _ = _make_plugin(
        _FakeResponse(
            200,
            json_error=ValueError("bad json"),
            text="<html><body><a href='/login'>Sign in</a></body></html>",
        )
    )

    status = asyncio.run(plugin.get_status())

    assert status == {"valid": False, "reason": "not_authenticated"}


def test_get_status_requires_dict_payload():
    plugin, _ = _make_plugin(_FakeResponse(200, payload=["unexpected"]))

    status = asyncio.run(plugin.get_status())

    assert status == {"valid": False, "reason": "not_authenticated"}


def test_validate_session_returns_boolean_status():
    plugin, _ = _make_plugin(_FakeResponse(200, {"user_type": "Active"}))

    assert asyncio.run(plugin.validate_session()) is True
