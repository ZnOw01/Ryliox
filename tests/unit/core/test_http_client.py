from __future__ import annotations

import asyncio

import httpx
import pytest

import config
from core.http_client import HttpClient

pytestmark = pytest.mark.unit


def test_http_client_retries_transient_request_error():
    client = HttpClient(cookies_file=config.COOKIES_FILE)
    attempts: dict[str, int] = {"count": 0}

    async def fake_get(url: str, **_kwargs):
        attempts["count"] += 1
        request = httpx.Request("GET", url)
        if attempts["count"] == 1:
            raise httpx.RequestError("transient", request=request)
        return httpx.Response(status_code=200, request=request, text="ok")

    client.client.get = fake_get  # type: ignore[method-assign]

    async def run():
        response = await client.get("https://example.com")
        assert response.status_code == 200
        await client.close()

    asyncio.run(run())
    assert attempts["count"] == 2
