from __future__ import annotations

import httpx
import pytest

import config
from core.http_client import HttpClient
from core.session_store import SessionStore

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_http_client_retries_transient_request_error():
    async with HttpClient(cookies_file=config.COOKIES_FILE) as client:
        attempts: dict[str, int] = {"count": 0}

        async def fake_get(url: str, **_kwargs):
            attempts["count"] += 1
            request = httpx.Request("GET", url)
            if attempts["count"] == 1:
                raise httpx.RequestError("transient", request=request)
            return httpx.Response(status_code=200, request=request, text="ok")

        client.client.get = fake_get  # type: ignore[method-assign]

        response = await client.get(f"{config.BASE_URL}/demo")
        assert response.status_code == 200
        assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_http_client_uses_async_context_manager():
    """Test that HTTP client works correctly with async context manager."""
    async with HttpClient(cookies_file=config.COOKIES_FILE) as client:
        # Verify client is initialized
        assert client.client is not None
        assert client._owns_client is True


@pytest.mark.asyncio
async def test_http_client_not_initialized_outside_context():
    """Test that HTTP client raises error when accessed outside context manager."""
    client = HttpClient(cookies_file=config.COOKIES_FILE)
    with pytest.raises(RuntimeError, match="not initialized"):
        _ = client.client


@pytest.mark.asyncio
async def test_http_client_loads_domain_and_path_specific_cookies(tmp_path):
    """Test that HTTP client can be initialized with a custom cookies file.

    This test verifies that the HTTP client accepts a custom cookies file path
    and initializes without errors. The actual cookie loading is tested through
    the SessionStore integration.
    """
    cookies_file = tmp_path / "test_cookies.json"
    cookies_file.write_text(
        '[{"name":"test","value":"123","domain":"example.com","path":"/"}]',
        encoding="utf-8",
    )

    # Verify that HttpClient can be created with the custom cookies file
    # without raising any exceptions
    client = HttpClient(cookies_file=cookies_file)
    assert client is not None

    # Verify the client works with context manager
    async with client as c:
        assert c.client is not None
        assert c._owns_client is True
        scoped = [cookie for cookie in c.client.cookies.jar if cookie.name == "test"]
        assert len(scoped) == 1
        assert scoped[0].domain == "example.com"
        assert scoped[0].path == "/"


@pytest.mark.asyncio
async def test_http_client_blocks_unsafe_absolute_url_before_request():
    async with HttpClient(cookies_file=config.COOKIES_FILE) as client:
        calls: dict[str, int] = {"count": 0}

        async def fake_get(url: str, **_kwargs):
            calls["count"] += 1
            request = httpx.Request("GET", url)
            return httpx.Response(status_code=200, request=request, text="ok")

        client.client.get = fake_get  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Blocked unsafe request URL"):
            await client.get("https://malicious.example/phishing")

        assert calls["count"] == 0


@pytest.mark.asyncio
async def test_http_client_blocks_unsafe_redirect_target():
    async with HttpClient(cookies_file=config.COOKIES_FILE) as client:
        calls: list[tuple[str, bool]] = []

        async def fake_get(url: str, **kwargs):
            calls.append((url, bool(kwargs.get("follow_redirects"))))
            request = httpx.Request("GET", url)
            if len(calls) == 1:
                return httpx.Response(
                    status_code=302,
                    headers={"location": "https://malicious.example/phishing"},
                    request=request,
                )
            return httpx.Response(status_code=200, request=request, text="ok")

        client.client.get = fake_get  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Blocked unsafe redirect URL"):
            await client.get(f"{config.BASE_URL}/redirect", allow_redirects=True)

        assert calls == [(f"{config.BASE_URL}/redirect", False)]


@pytest.mark.asyncio
async def test_http_client_enforces_numeric_redirect_limit(monkeypatch):
    monkeypatch.setattr(config.SETTINGS.http, "max_redirects", 2)
    async with HttpClient(cookies_file=config.COOKIES_FILE) as client:

        async def fake_get(url: str, **_kwargs):
            request = httpx.Request("GET", url)
            number = int(url.rsplit("/", 1)[-1])
            return httpx.Response(302, headers={"location": f"/{number + 1}"}, request=request)

        client.client.get = fake_get  # type: ignore[method-assign]
        with pytest.raises(ValueError, match="Redirect limit exceeded"):
            await client.get(f"{config.BASE_URL}/0", allow_redirects=True)


@pytest.mark.asyncio
async def test_http_client_rejects_oversized_upstream_response(monkeypatch):
    monkeypatch.setattr(config.SETTINGS.http, "max_response_size_mb", 1)
    async with HttpClient(cookies_file=config.COOKIES_FILE) as client:

        async def fake_get(url: str, **_kwargs):
            request = httpx.Request("GET", url)
            return httpx.Response(200, request=request, content=b"x" * (1024 * 1024 + 1))

        client.client.get = fake_get  # type: ignore[method-assign]
        with pytest.raises(ValueError, match="size limit"):
            await client.get(f"{config.BASE_URL}/large")


@pytest.mark.asyncio
async def test_http_client_persists_refreshed_set_cookie(monkeypatch, tmp_path):
    db_path = tmp_path / "session.sqlite3"
    cookies_file = tmp_path / "cookies.json"
    monkeypatch.setattr(config, "SESSION_DB_FILE", db_path)
    monkeypatch.setattr(config, "COOKIES_FILE", cookies_file)

    store = SessionStore(db_path=db_path, legacy_cookies_file=cookies_file)
    store.save_cookies({"orm-jwt": "old-token", "orm-rt": "refresh-token"})

    async with HttpClient() as client:
        request = httpx.Request("GET", f"{config.BASE_URL}/profile/")

        async def fake_get(url: str, **_kwargs):
            assert url == f"{config.BASE_URL}/profile/"
            return httpx.Response(
                status_code=200,
                headers={"set-cookie": "orm-jwt=new-token; Path=/; HttpOnly; Secure"},
                request=request,
                json={"user_type": "Active"},
            )

        client.client.get = fake_get  # type: ignore[method-assign]

        response = await client.get("/profile/")

    assert response.status_code == 200
    assert SessionStore(db_path=db_path, legacy_cookies_file=cookies_file).get_cookies() == {
        "orm-jwt": "new-token",
        "orm-rt": "refresh-token",
    }


@pytest.mark.asyncio
async def test_http_client_preserves_unmodified_cookie_scope_on_refresh(monkeypatch, tmp_path):
    db_path = tmp_path / "session.sqlite3"
    cookies_file = tmp_path / "cookies.json"
    monkeypatch.setattr(config, "SESSION_DB_FILE", db_path)
    monkeypatch.setattr(config, "COOKIES_FILE", cookies_file)
    store = SessionStore(db_path=db_path, legacy_cookies_file=cookies_file)
    store.save_cookies(
        [
            {
                "name": "orm-rt",
                "value": "refresh-token",
                "domain": "learning.oreilly.com",
                "path": "/library",
                "secure": True,
            }
        ]
    )

    async with HttpClient() as client:
        request = httpx.Request("GET", f"{config.BASE_URL}/profile/")

        async def fake_get(url: str, **_kwargs):
            return httpx.Response(
                200,
                headers={"set-cookie": "orm-jwt=new-token; Path=/; HttpOnly; Secure"},
                request=request,
            )

        client.client.get = fake_get  # type: ignore[method-assign]
        await client.get("/profile/")

    records = store.get_cookie_records()
    refresh = next(record for record in records if record["name"] == "orm-rt")
    assert refresh["domain"] == "learning.oreilly.com"
    assert refresh["path"] == "/library"
    assert refresh["secure"] is True


def test_jwt_status_decodes_base64url_payload():
    """JWT segments are base64url: '-' and '_' must decode, not mark the token invalid."""
    import base64
    import json
    import time

    payload = json.dumps({"exp": int(time.time()) + 3600, "sub": "user?>?>"}).encode()
    segment = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    assert "-" in segment or "_" in segment

    client = HttpClient(cookies_file=config.COOKIES_FILE)
    client._auth_cookies = {"orm-jwt": f"header.{segment}.signature"}

    status = client.get_jwt_status()

    assert status is not None
    assert status["valid"] is True


@pytest.mark.asyncio
async def test_http_client_does_not_store_a_session_from_anti_bot_cookies_alone(
    monkeypatch, tmp_path
):
    """Akamai sets _abck/bm_* on every response, even with no session at all.

    Persisting them into an empty store made the app report saved cookies the user never
    pasted, and the book routes skipped the "configure your cookies" answer.
    """
    db_path = tmp_path / "session.sqlite3"
    cookies_file = tmp_path / "cookies.json"
    monkeypatch.setattr(config, "SESSION_DB_FILE", db_path)
    monkeypatch.setattr(config, "COOKIES_FILE", cookies_file)

    async with HttpClient() as client:
        request = httpx.Request("GET", f"{config.BASE_URL}/api/v2/search/")

        async def fake_get(url: str, **_kwargs):
            return httpx.Response(
                status_code=403,
                headers=[
                    ("content-type", "text/html"),
                    ("set-cookie", "_abck=sensor; Path=/; Domain=.oreilly.com"),
                    ("set-cookie", "bm_sz=size; Path=/; Domain=.oreilly.com"),
                ],
                request=request,
                text="<HTML><TITLE>Access Denied</TITLE></HTML>",
            )

        client.client.get = fake_get  # type: ignore[method-assign]
        await client.get("/api/v2/search/")

    assert SessionStore(db_path=db_path, legacy_cookies_file=cookies_file).get_cookies() == {}


@pytest.mark.asyncio
async def test_http_client_refreshes_anti_bot_cookies_of_a_saved_session(monkeypatch, tmp_path):
    db_path = tmp_path / "session.sqlite3"
    cookies_file = tmp_path / "cookies.json"
    monkeypatch.setattr(config, "SESSION_DB_FILE", db_path)
    monkeypatch.setattr(config, "COOKIES_FILE", cookies_file)
    SessionStore(db_path=db_path, legacy_cookies_file=cookies_file).save_cookies(
        {"orm-jwt": "token", "_abck": "old"}
    )

    async with HttpClient() as client:
        request = httpx.Request("GET", f"{config.BASE_URL}/api/v2/search/")

        async def fake_get(url: str, **_kwargs):
            return httpx.Response(
                status_code=200,
                headers={"set-cookie": "_abck=new; Path=/"},
                request=request,
                json={"results": []},
            )

        client.client.get = fake_get  # type: ignore[method-assign]
        await client.get("/api/v2/search/")

    stored = SessionStore(db_path=db_path, legacy_cookies_file=cookies_file).get_cookies()
    assert stored == {"orm-jwt": "token", "_abck": "new"}
