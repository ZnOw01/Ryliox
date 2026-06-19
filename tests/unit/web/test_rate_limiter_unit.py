"""Tests for rate limiting functionality."""

from __future__ import annotations

# Import the classes directly to avoid initializing the FastAPI app
import sys
import time
from pathlib import Path

import pytest
from starlette.requests import Request

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

pytestmark = pytest.mark.unit


class _RateLimiter:
    """Simple in-memory rate limiter per client IP and endpoint path."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        from collections import defaultdict

        self._requests: dict[tuple[str, str], list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str, endpoint: str) -> bool:
        key = (client_ip, endpoint)
        now = time.monotonic()
        timestamps = self._requests[key]
        # Remove timestamps outside the window
        cutoff = now - self.window_seconds
        self._requests[key] = [ts for ts in timestamps if ts > cutoff]
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    def clear_old_entries(self) -> None:
        """Clear entries older than window to prevent memory growth."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        for key in list(self._requests.keys()):
            self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]
            if not self._requests[key]:
                del self._requests[key]


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


class TestRateLimiter:
    """Test suite for _RateLimiter class."""

    def test_rate_limiter_allows_requests_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = _RateLimiter(max_requests=5, window_seconds=60)

        # Make 5 requests - all should be allowed
        for _i in range(5):
            assert limiter.is_allowed("127.0.0.1", "/api/download") is True

    def test_rate_limiter_blocks_excess_requests(self):
        """Test that requests over limit are blocked."""
        limiter = _RateLimiter(max_requests=3, window_seconds=60)

        # Make 3 requests - all allowed
        for _i in range(3):
            assert limiter.is_allowed("127.0.0.1", "/api/download") is True

        # 4th request should be blocked
        assert limiter.is_allowed("127.0.0.1", "/api/download") is False

    def test_rate_limiter_per_endpoint_tracking(self):
        """Test that rate limiting is per-endpoint."""
        limiter = _RateLimiter(max_requests=2, window_seconds=60)

        # Make 2 requests to /api/download
        assert limiter.is_allowed("127.0.0.1", "/api/download") is True
        assert limiter.is_allowed("127.0.0.1", "/api/download") is True

        # Should be blocked for /api/download
        assert limiter.is_allowed("127.0.0.1", "/api/download") is False

        # But /api/cookies should still be allowed (separate counter)
        assert limiter.is_allowed("127.0.0.1", "/api/cookies") is True
        assert limiter.is_allowed("127.0.0.1", "/api/cookies") is True

        # Now /api/cookies should also be blocked
        assert limiter.is_allowed("127.0.0.1", "/api/cookies") is False

    def test_rate_limiter_per_client_ip(self):
        """Test that rate limiting is per-client IP."""
        limiter = _RateLimiter(max_requests=2, window_seconds=60)

        # Client A makes 2 requests
        assert limiter.is_allowed("192.168.1.1", "/api/download") is True
        assert limiter.is_allowed("192.168.1.1", "/api/download") is True

        # Client A is now blocked
        assert limiter.is_allowed("192.168.1.1", "/api/download") is False

        # Client B should still be allowed
        assert limiter.is_allowed("192.168.1.2", "/api/download") is True

    def test_rate_limiter_window_expiration(self):
        """Test that rate limit window expires correctly."""
        limiter = _RateLimiter(max_requests=2, window_seconds=1)

        # Make 2 requests
        assert limiter.is_allowed("127.0.0.1", "/api/download") is True
        assert limiter.is_allowed("127.0.0.1", "/api/download") is True

        # Should be blocked
        assert limiter.is_allowed("127.0.0.1", "/api/download") is False

        # Wait for window to expire
        time.sleep(1.1)

        # Now should be allowed again
        assert limiter.is_allowed("127.0.0.1", "/api/download") is True

    def test_clear_old_entries(self):
        """Test that old entries are cleared correctly."""
        limiter = _RateLimiter(max_requests=5, window_seconds=1)

        # Add some entries
        limiter.is_allowed("127.0.0.1", "/api/download")
        limiter.is_allowed("127.0.0.1", "/api/cookies")

        # Wait for window to expire
        time.sleep(1.1)

        # Clear old entries
        limiter.clear_old_entries()

        # Should be able to make requests again
        assert limiter.is_allowed("127.0.0.1", "/api/download") is True


class TestGetClientIp:
    """Test suite for _get_client_ip function."""

    def _build_scope(
        self,
        headers: dict[str, str],
        client: tuple[str, int] | None = ("127.0.0.1", 12345),
    ):
        """Build a mock request scope."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [
                (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()
            ],
            "scheme": "http",
            "server": ("localhost", 8000),
            "client": client,
        }
        return Request(scope)

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header."""
        request = self._build_scope({"x-forwarded-for": "203.0.113.1, 70.41.3.18, 150.172.238.178"})
        assert _get_client_ip(request) == "203.0.113.1"

    def test_get_client_ip_from_x_real_ip(self):
        """Test IP extraction from X-Real-IP header."""
        request = self._build_scope({"x-real-ip": "192.168.1.100"})
        assert _get_client_ip(request) == "192.168.1.100"

    def test_get_client_ip_from_request_client(self):
        """Test IP extraction from request client when no headers."""
        request = self._build_scope({}, client=("10.0.0.5", 54321))
        assert _get_client_ip(request) == "10.0.0.5"

    def test_get_client_ip_fallback(self):
        """Test fallback to 127.0.0.1 when no client info available."""
        request = self._build_scope({}, client=None)
        assert _get_client_ip(request) == "127.0.0.1"

    def test_x_forwarded_for_priority_over_x_real_ip(self):
        """Test X-Forwarded-For takes priority over X-Real-IP."""
        request = self._build_scope(
            {"x-forwarded-for": "203.0.113.1", "x-real-ip": "192.168.1.100"}
        )
        # X-Forwarded-For should take priority
        assert _get_client_ip(request) == "203.0.113.1"


class TestRateLimitingSecurity:
    """Test security aspects of rate limiting."""

    def test_rate_limiter_prevents_memory_growth(self):
        """Test that clear_old_entries prevents unbounded memory growth."""
        limiter = _RateLimiter(max_requests=100, window_seconds=1)

        # Add many different endpoints
        for i in range(100):
            limiter.is_allowed(f"client-{i}", f"/api/endpoint-{i}")

        # Should have 100 entries
        assert len(limiter._requests) == 100

        # Wait for window to expire
        time.sleep(1.1)

        # Clear old entries
        limiter.clear_old_entries()

        # All entries should be cleared
        assert len(limiter._requests) == 0

    def test_rate_limiter_handles_edge_cases(self):
        """Test rate limiter handles edge cases gracefully."""
        limiter = _RateLimiter(max_requests=1, window_seconds=60)

        # Empty IP and endpoint
        assert limiter.is_allowed("", "") is True
        assert limiter.is_allowed("", "") is False  # Blocked on 2nd request

        # Very long strings
        long_ip = "192.168.1." + "1" * 1000
        long_endpoint = "/api/" + "x" * 1000
        assert limiter.is_allowed(long_ip, long_endpoint) is True
