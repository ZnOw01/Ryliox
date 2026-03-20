from __future__ import annotations

import asyncio

import httpx
import pytest

import config
from core.http_client import HttpClient

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_http_client_retries_transient_request_error():
    client = HttpClient(cookies_file=config.COOKIES_FILE)
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
    await client.close()
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_http_client_blocks_unsafe_absolute_request_urls():
    client = HttpClient(cookies_file=config.COOKIES_FILE)

    with pytest.raises(ValueError, match="Blocked unsafe request URL"):
        await client.get("https://example.com/demo")
    await client.close()


@pytest.mark.asyncio
async def test_http_client_follows_safe_redirects():
    client = HttpClient(cookies_file=config.COOKIES_FILE)
    attempts: dict[str, int] = {"count": 0}

    async def fake_get(url: str, **kwargs):
        attempts["count"] += 1
        request = httpx.Request("GET", url)
        if attempts["count"] == 1:
            return httpx.Response(
                status_code=302,
                headers={"location": "/final"},
                request=request,
            )
        return httpx.Response(status_code=200, request=request, text="ok")

    client.client.get = fake_get  # type: ignore[method-assign]

    response = await client.get(f"{config.BASE_URL}/start", follow_redirects=True)
    assert response.status_code == 200
    assert str(response.request.url) == f"{config.BASE_URL}/final"
    await client.close()
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_http_client_blocks_unsafe_redirects():
    client = HttpClient(cookies_file=config.COOKIES_FILE)
    attempts: dict[str, int] = {"count": 0}

    async def fake_get(url: str, **kwargs):
        attempts["count"] += 1
        request = httpx.Request("GET", url)
        return httpx.Response(
            status_code=302,
            headers={"location": "https://example.com/pwn"},
            request=request,
        )

    client.client.get = fake_get  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="Blocked unsafe redirect URL"):
        await client.get(f"{config.BASE_URL}/start", follow_redirects=True)
    await client.close()
    assert attempts["count"] == 1


@pytest.mark.asyncio
async def test_http_client_loads_domain_and_path_specific_cookies(tmp_path):
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text(
        """
        [
          {"name":"sessionid","value":"root","domain":"learning.oreilly.com","path":"/"},
          {"name":"sessionid","value":"library","domain":"learning.oreilly.com","path":"/library"}
        ]
        """.strip(),
        encoding="utf-8",
    )

    client = HttpClient(cookies_file=cookies_file)

    try:
        cookies = list(client.client.cookies.jar)
        assert len(cookies) == 2
        assert {cookie.path for cookie in cookies} == {"/", "/library"}
    finally:
        await client.close()
