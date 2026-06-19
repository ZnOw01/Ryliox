"""Integration tests for Authentication API endpoints.

Tests cover:
- Session status checking
- Cookie management
- Same-origin protection
- Rate limiting on sensitive endpoints
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
class TestAuthStatus:
    """Tests for GET /api/status endpoint."""

    def test_status_no_session(self, test_client: TestClient, mock_kernel, mock_session_store):
        """Test status check with no valid session."""
        # Clear cookies so has_cookies reflects the empty state
        mock_session_store.save_cookies({})

        # Mock auth to return invalid status
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": False, "reason": "no_session"}
        )

        response = test_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "no_session"
        assert data["has_cookies"] is False

    def test_status_valid_session(self, authenticated_client: TestClient, mock_kernel):
        """Test status check with valid session."""
        # Mock auth to return valid status
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        response = authenticated_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["reason"] is None
        assert data["has_cookies"] is True

    def test_status_network_error(self, test_client: TestClient, mock_kernel):
        """Test status check when network error occurs."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": False, "reason": "network_error"}
        )

        response = test_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "network_error"


@pytest.mark.integration
class TestSaveCookies:
    """Tests for POST /api/cookies endpoint."""

    def test_save_valid_cookies_same_origin(
        self, test_client: TestClient, sample_cookies, mock_kernel
    ):
        """Test saving valid cookies with same-origin header."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        response = test_client.post(
            "/api/cookies",
            json=sample_cookies,
            headers={"Origin": "http://testserver"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_save_cookies_cross_origin_blocked(self, test_client: TestClient, sample_cookies):
        """Test that cross-origin cookie saving is blocked."""
        response = test_client.post(
            "/api/cookies",
            json=sample_cookies,
            headers={"Origin": "https://malicious-site.com"},
        )

        assert response.status_code == 403
        data = response.json()
        detail = data if "error" in data else data.get("detail", {})
        assert "Cross-origin request blocked" in detail.get("error", "")

    def test_save_cookies_invalid_payload(self, test_client: TestClient, mock_kernel):
        """Test saving invalid cookie payload."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        response = test_client.post(
            "/api/cookies",
            json={"invalid": {"nested": "object"}},  # Invalid cookie structure
            headers={"Origin": "http://testserver"},
        )

        # Should still succeed as empty cookies are normalized
        assert response.status_code in [200, 400]

    def test_save_cookies_unauthorized_session(
        self, test_client: TestClient, sample_cookies, mock_kernel
    ):
        """Test that cookies are reverted when session validation fails."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": False, "reason": "invalid_cookies"}
        )

        response = test_client.post(
            "/api/cookies",
            json=sample_cookies,
            headers={"Origin": "http://testserver"},
        )

        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", data)
        assert "Cookies saved but session is still invalid" in detail.get("error", "")

    def test_save_cookies_empty_payload(self, test_client: TestClient):
        """Test saving empty cookie payload."""
        response = test_client.post(
            "/api/cookies", json={}, headers={"Origin": "http://testserver"}
        )

        # Should return 400 for invalid payload
        assert response.status_code == 400

    def test_save_cookies_none_payload(self, test_client: TestClient):
        """Test saving None as cookie payload."""
        response = test_client.post(
            "/api/cookies", json=None, headers={"Origin": "http://testserver"}
        )

        assert response.status_code == 400


@pytest.mark.integration
class TestGetCookies:
    """Tests for GET /api/cookies endpoint."""

    def test_get_cookies_same_origin(self, authenticated_client: TestClient, sample_cookies):
        """Test retrieving cookies with same-origin header."""
        response = authenticated_client.get(
            "/api/cookies", headers={"Origin": "http://testserver"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "cookies" in data
        # Cookies should match what was saved
        assert data["cookies"] == sample_cookies

    def test_get_cookies_cross_origin_blocked(self, test_client: TestClient):
        """Test that cross-origin cookie retrieval is blocked."""
        response = test_client.get("/api/cookies", headers={"Origin": "https://malicious-site.com"})

        assert response.status_code == 403
        data = response.json()
        detail = data if "error" in data else data.get("detail", {})
        assert "Cross-origin request blocked" in detail.get("error", "")

    def test_get_cookies_no_origin_header_safe_method(self, test_client: TestClient):
        """Test GET request without Origin header (should be allowed for safe methods)."""
        response = test_client.get("/api/cookies")

        assert response.status_code == 200

    def test_get_empty_cookies(self, test_client: TestClient, mock_session_store):
        """Test retrieving cookies when none are stored."""
        mock_session_store.save_cookies({})
        response = test_client.get("/api/cookies")

        assert response.status_code == 200
        data = response.json()
        assert data["cookies"] == {}


@pytest.mark.integration
@pytest.mark.rate_limit
class TestAuthRateLimiting:
    """Tests for rate limiting on authentication endpoints."""

    def test_cookies_endpoint_rate_limited(
        self, test_client: TestClient, sample_cookies, mock_kernel
    ):
        """Test that POST /api/cookies is rate limited."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        # Make multiple rapid requests
        headers = {"Origin": "http://testserver"}
        responses = []
        for _ in range(10):
            response = test_client.post("/api/cookies", json=sample_cookies, headers=headers)
            responses.append(response.status_code)

        # At least one should be rate limited (429)
        assert 429 in responses, "Expected at least one rate-limited response"

    def test_status_endpoint_not_rate_limited(self, test_client: TestClient):
        """Test that GET /api/status is not rate limited."""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = test_client.get("/api/status")
            responses.append(response.status_code)

        # All should succeed
        assert all(r == 200 for r in responses), "GET /api/status should not be rate limited"


@pytest.mark.integration
class TestCookieFormats:
    """Tests for various cookie payload formats."""

    def test_cookie_string_format(self, test_client: TestClient, mock_kernel):
        """Test saving cookies in string format (Cookie header style)."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        cookie_string = "session_id=test123; auth_token=token456; user_id=user789"

        response = test_client.post(
            "/api/cookies",
            json=cookie_string,
            headers={"Origin": "http://testserver"},
        )

        assert response.status_code == 200

        # Verify cookies were saved correctly
        get_response = test_client.get("/api/cookies")
        data = get_response.json()
        assert data["cookies"]["session_id"] == "test123"
        assert data["cookies"]["auth_token"] == "token456"

    def test_edithiscookie_format(self, test_client: TestClient, mock_kernel):
        """Test saving cookies in EditThisCookie format."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        edithiscookie_format = [
            {"name": "session_id", "value": "test123", "domain": ".oreilly.com"},
            {"name": "auth_token", "value": "token456", "domain": ".oreilly.com"},
        ]

        response = test_client.post(
            "/api/cookies",
            json=edithiscookie_format,
            headers={"Origin": "http://testserver"},
        )

        assert response.status_code == 200

        # Verify cookies were saved
        get_response = test_client.get("/api/cookies")
        data = get_response.json()
        assert data["cookies"]["session_id"] == "test123"

    def test_cookie_dict_with_nested_cookies_field(self, test_client: TestClient, mock_kernel):
        """Test saving cookies with nested 'cookies' field."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        nested_format = {
            "cookies": [
                {"name": "session_id", "value": "test123"},
                {"name": "auth_token", "value": "token456"},
            ]
        }

        response = test_client.post(
            "/api/cookies",
            json=nested_format,
            headers={"Origin": "http://testserver"},
        )

        assert response.status_code == 200


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling in auth endpoints."""

    def test_auth_plugin_error(self, test_client: TestClient, mock_kernel):
        """Test handling when auth plugin raises an exception."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            side_effect=Exception("Auth plugin error")
        )

        response = test_client.get("/api/status")

        # Should handle gracefully
        assert response.status_code in [200, 500]

    def test_session_store_error(self, test_client: TestClient, mock_kernel, monkeypatch):
        """Test handling when session store is unavailable."""
        mock_kernel._plugins["auth"].get_status = AsyncMock(
            return_value={"valid": True, "reason": None}
        )

        # Corrupt the session store
        from core.session_store import SessionStore

        monkeypatch.setattr(
            SessionStore,
            "get_cookies",
            lambda self: (_ for _ in ()).throw(Exception("DB Error")),
        )

        response = test_client.get("/api/status")

        # Restore original method
        monkeypatch.undo()

        # Should handle gracefully
        assert response.status_code in [200, 500]
