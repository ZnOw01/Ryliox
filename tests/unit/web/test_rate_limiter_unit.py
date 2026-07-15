from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.requests import Request

from web.server import _client_ip, _RateLimiter

pytestmark = pytest.mark.unit


def _request(client: tuple[str, int] | None = ("127.0.0.1", 12345)) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [],
            "scheme": "http",
            "server": ("localhost", 8000),
            "client": client,
        }
    )


def test_rate_limiter_enforces_limit_per_client_and_endpoint() -> None:
    limiter = _RateLimiter(max_requests=2, window_seconds=60)

    assert limiter.is_allowed("client-a", "/api/download") is True
    assert limiter.is_allowed("client-a", "/api/download") is True
    assert limiter.is_allowed("client-a", "/api/download") is False
    assert limiter.is_allowed("client-b", "/api/download") is True
    assert limiter.is_allowed("client-a", "/api/cookies") is True


def test_rate_limiter_prunes_stale_keys_during_normal_requests() -> None:
    limiter = _RateLimiter(max_requests=2, window_seconds=10)

    with patch("web.server.time.monotonic", side_effect=[1.0, 20.0]):
        limiter._last_cleanup = 0.0
        assert limiter.is_allowed("old-client", "/api/download") is True
        assert limiter.is_allowed("new-client", "/api/download") is True

    assert ("old-client", "/api/download") not in limiter._requests
    assert ("new-client", "/api/download") in limiter._requests


def test_client_ip_uses_transport_peer_not_spoofable_forwarded_headers() -> None:
    assert _client_ip(_request(("10.0.0.5", 54321))) == "10.0.0.5"
    assert _client_ip(_request(None)) == "unknown"
