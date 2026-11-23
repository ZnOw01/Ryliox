"""The upstream client must look like the browser whose session it carries.

O'Reilly sits behind Akamai, which answers a real session with "Access Denied" when the
client's TLS fingerprint is Python's or when the browser's _abck/bm_* cookies are missing.
"""

from __future__ import annotations

import httpx
import pytest

import config
from core.browser_transport import BrowserTransport
from core.http_client import HttpClient

pytestmark = pytest.mark.unit


def _settings_with(**http: object) -> config.HttpSettings:
    return config.HttpSettings(**http)


def test_requests_go_through_the_browser_transport_by_default():
    assert config.HttpSettings().impersonate == "chrome"


@pytest.mark.asyncio
async def test_client_uses_the_browser_transport(monkeypatch, tmp_path):
    monkeypatch.setattr(config.SETTINGS.http, "impersonate", "chrome")
    async with HttpClient(cookies_file=tmp_path / "none.json") as client:
        assert isinstance(client.client._transport, BrowserTransport)


@pytest.mark.asyncio
async def test_empty_impersonate_keeps_plain_httpx(monkeypatch, tmp_path):
    monkeypatch.setattr(config.SETTINGS.http, "impersonate", "")
    async with HttpClient(cookies_file=tmp_path / "none.json") as client:
        assert not isinstance(client.client._transport, BrowserTransport)


def test_impersonation_sends_no_hardcoded_user_agent():
    # A Chrome-124-on-Linux User-Agent over another browser's handshake is a mismatch
    # anti-bot systems look for. The impersonated profile supplies a matching one.
    assert "User-Agent" not in config.request_headers(_settings_with(impersonate="chrome"))


def test_plain_httpx_still_sends_browser_like_headers():
    headers = config.request_headers(_settings_with(impersonate=""))
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert headers["Accept-Language"]


def test_a_configured_user_agent_is_honoured():
    headers = config.request_headers(_settings_with(impersonate="chrome", user_agent="Custom/1"))
    assert headers["User-Agent"] == "Custom/1"


def test_akamai_cookies_from_the_browser_are_kept(tmp_path):
    cookies = tmp_path / "cookies.json"
    cookies.write_text(
        '{"orm-jwt": "jwt", "_abck": "sensor", "bm_sz": "size", "ak_bmsc": "x", "groot_sessionid": "s"}',
        encoding="utf-8",
    )
    client = HttpClient(cookies_file=cookies)
    client._load_cookies(cookies)

    assert {"_abck", "bm_sz", "ak_bmsc", "orm-jwt"} <= set(client._auth_cookies)


class _FakeCurlResponse:
    status_code = 200
    content = b'{"ok": true}'

    class headers:  # noqa: N801 - mimics curl_cffi's Headers.multi_items()
        @staticmethod
        def multi_items():
            return [
                ("content-type", "application/json"),
                ("content-encoding", "br"),
                ("set-cookie", "bm_sv=new; Path=/"),
                ("set-cookie", "orm-jwt=fresh; Path=/"),
            ]


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return _FakeCurlResponse()

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_transport_hands_httpx_requests_to_curl_and_back():
    transport = BrowserTransport("chrome")
    fake = _FakeSession()
    transport._session = fake  # type: ignore[assignment]

    async with httpx.AsyncClient(transport=transport, headers={"Accept-Language": "es"}) as client:
        client.cookies.set("orm-jwt", "jwt", domain="learning.oreilly.com")
        response = await client.get("https://learning.oreilly.com/api/v2/search/?query=x")

    sent = fake.calls[0]
    names = {name.lower() for name, _ in sent["headers"]}
    # httpx's own defaults would contradict the browser profile.
    assert "user-agent" not in names
    assert "connection" not in names and "host" not in names
    assert ("accept-language", "es") in [(n.lower(), v) for n, v in sent["headers"]]
    assert ("cookie", "orm-jwt=jwt") in [(n.lower(), v) for n, v in sent["headers"]]
    # Redirects are validated hop by hop by HttpClient; cookies belong to httpx's jar.
    assert sent["allow_redirects"] is False
    assert sent["discard_cookies"] is True

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    # curl already decoded the body, and both Set-Cookie headers reach httpx's jar.
    assert "content-encoding" not in response.headers
    assert client.cookies.get("orm-jwt") == "fresh"
    assert client.cookies.get("bm_sv") == "new"


@pytest.mark.asyncio
async def test_transport_maps_curl_failures_to_httpx_errors():
    from curl_cffi.requests import exceptions as curl_errors

    class Failing(_FakeSession):
        def __init__(self, exc):
            super().__init__()
            self.exc = exc

        async def request(self, method, url, **kwargs):
            raise self.exc

    for exc, expected in [
        (curl_errors.ReadTimeout("slow"), httpx.TimeoutException),
        (curl_errors.DNSError("no host"), httpx.ConnectError),
        (curl_errors.RequestException("other"), httpx.TransportError),
    ]:
        transport = BrowserTransport("chrome")
        transport._session = Failing(exc)  # type: ignore[assignment]
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(expected):
                await client.get("https://learning.oreilly.com/")
