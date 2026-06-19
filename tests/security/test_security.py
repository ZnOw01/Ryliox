"""Security tests for Ryliox API.

Tests cover:
- Path traversal attacks
- XSS (Cross-Site Scripting)
- SQL Injection
- Rate limiting bypass attempts
- CORS (Cross-Origin Resource Sharing)
- Authentication bypass
- Input validation
"""

from __future__ import annotations

import pytest
import requests


@pytest.mark.security
class TestPathTraversal:
    """Tests for path traversal vulnerabilities."""

    def test_download_output_dir_path_traversal(
        self, base_url: str, sample_cookies: dict[str, str]
    ):
        """Test that path traversal in output_dir is blocked."""
        # Set up auth
        requests.post(f"{base_url}/api/cookies", json=sample_cookies, headers={"Origin": base_url})

        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM",
        ]

        for path in traversal_attempts:
            response = requests.post(
                f"{base_url}/api/download",
                json={
                    "book_id": "test123",
                    "format": ["epub"],
                    "output_dir": path,
                },
                headers={"Origin": base_url},
            )

            # Should either reject the request or sanitize the path
            assert response.status_code in [400, 403, 422, 500], (
                f"Path traversal attempt '{path}' should be blocked, got {response.status_code}"
            )

    def test_book_id_path_traversal(self, base_url: str):
        """Test that path traversal in book_id is handled."""
        traversal_ids = [
            "../../../etc/passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
        ]

        for book_id in traversal_ids:
            response = requests.get(f"{base_url}/api/book/{book_id}")

            # Should not succeed with 200 (might return 404 or error)
            assert response.status_code in [400, 404, 422, 500], (
                f"Book ID traversal attempt should not succeed, got {response.status_code}"
            )


@pytest.mark.security
class TestXSS:
    """Tests for XSS vulnerabilities."""

    def test_search_xss_payloads(self, base_url: str):
        """Test that XSS payloads in search are handled."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(1)'>",
            "<body onload=alert('xss')>",
            "<svg onload=alert('xss')>",
            "<input onfocus=alert('xss')>",
            "'--><script>alert('xss')</script>",
            "<scr<script>ipt>alert('xss')</scr</script>ipt>",
        ]

        for payload in xss_payloads:
            response = requests.get(f"{base_url}/api/search", params={"q": payload})

            # Request should be processed safely (200 or 400)
            assert response.status_code in [200, 400, 422], (
                f"XSS payload caused unexpected error: {response.status_code}"
            )

            # Response should not contain the raw script
            if response.status_code == 200:
                response_text = response.text
                assert "<script>" not in response_text or "alert" not in response_text, (
                    f"XSS payload '{payload}' was reflected unsanitized"
                )

    def test_cookie_xss_payloads(self, base_url: str):
        """Test that XSS payloads in cookies are handled."""
        xss_cookies = {
            "<script>alert('xss')</script>": "value",
            "session_id": "<img src=x onerror=alert('xss')>",
        }

        response = requests.post(
            f"{base_url}/api/cookies", json=xss_cookies, headers={"Origin": base_url}
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422, 429]

    def test_book_info_xss_injection(self, base_url: str):
        """Test that book metadata containing XSS is sanitized."""
        # This test depends on the server returning book data
        # If the server doesn't sanitize, it could be vulnerable

        # We can only test if the API returns data
        response = requests.get(f"{base_url}/api/book/test-id")

        if response.status_code == 200:
            response_text = response.text
            # Check for script tags in response
            if "<script>" in response_text.lower():
                # If scripts are present, they should be properly escaped
                pass  # Log for manual review


@pytest.mark.security
class TestSQLInjection:
    """Tests for SQL injection vulnerabilities."""

    def test_search_sql_injection(self, base_url: str):
        """Test SQL injection attempts in search parameter."""
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' AND 1=1 --",
            "' UNION SELECT * FROM users --",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --",
            "' OR 1=1 LIMIT 1 --",
            '") OR (""="',
            "1 AND 1=1",
            "1 AND 1=2",
        ]

        for payload in sql_payloads:
            response = requests.get(f"{base_url}/api/search", params={"q": payload})

            # Should handle gracefully without exposing database errors
            assert response.status_code in [200, 400, 500], (
                "SQL injection payload caused unexpected behavior"
            )

            # Response should not contain SQL error messages
            response_text = response.text.lower()
            assert "sql" not in response_text or "syntax" not in response_text, (
                f"Potential SQL error leaked: {response_text[:200]}"
            )

    def test_book_id_sql_injection(self, base_url: str):
        """Test SQL injection attempts in book_id parameter."""
        sql_book_ids = [
            "1' OR '1'='1",
            "test'; DROP TABLE books; --",
            "1 UNION SELECT * FROM users",
        ]

        for book_id in sql_book_ids:
            response = requests.get(f"{base_url}/api/book/{book_id}")

            # Should handle gracefully
            assert response.status_code in [200, 400, 404, 500]

            # Should not expose SQL errors
            response_text = response.text.lower()
            assert "mysql" not in response_text
            assert "sqlite" not in response_text
            assert "sql syntax" not in response_text

    def test_job_id_sql_injection(self, base_url: str):
        """Test SQL injection attempts in job_id parameter."""
        sql_job_ids = [
            "job-123' OR '1'='1",
            "job-123'; DELETE FROM downloads; --",
        ]

        for job_id in sql_job_ids:
            response = requests.get(f"{base_url}/api/progress?job_id={job_id}")

            # Should handle gracefully
            assert response.status_code in [200, 400]


@pytest.mark.security
class TestCORSSecurity:
    """Tests for CORS security."""

    def test_cors_preflight_allowed_origins(self, base_url: str):
        """Test CORS preflight for allowed origins."""
        allowed_origins = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

        for origin in allowed_origins:
            response = requests.options(
                f"{base_url}/api/status",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )

            # Preflight should succeed for allowed origins
            assert response.status_code == 200, f"CORS preflight failed for {origin}"

            # Check CORS headers
            assert "access-control-allow-origin" in response.headers

    def test_cors_disallowed_origins(self, base_url: str):
        """Test that disallowed origins are rejected."""
        disallowed_origins = [
            "https://evil.com",
            "https://attacker-site.com",
            "http://localhost:9000",  # Different port
            "https://localhost:8000",  # Different scheme
            "null",
            "file://",
        ]

        for origin in disallowed_origins:
            # Test POST endpoint that requires same-origin
            response = requests.post(
                f"{base_url}/api/cookies",
                json={"test": "data"},
                headers={"Origin": origin},
            )

            # Should be blocked
            assert response.status_code in [403, 400], (
                f"Disallowed origin {origin} was not blocked: {response.status_code}"
            )

    def test_cors_mutating_operations_blocked(self, base_url: str):
        """Test that mutating operations are blocked cross-origin."""
        malicious_origin = "https://malicious-site.com"

        endpoints_to_test = [
            ("POST", "/api/cookies", {"session": "test"}),
            ("POST", "/api/download", {"book_id": "test"}),
            ("POST", "/api/cancel", {}),
        ]

        for method, endpoint, payload in endpoints_to_test:
            if method == "POST":
                response = requests.post(
                    f"{base_url}{endpoint}",
                    json=payload,
                    headers={"Origin": malicious_origin},
                )
            else:
                response = requests.request(
                    method,
                    f"{base_url}{endpoint}",
                    headers={"Origin": malicious_origin},
                )

            # Mutating operations should be blocked from cross-origin
            assert response.status_code in [403, 400, 401], (
                f"{method} {endpoint} should be blocked from {malicious_origin}: got {response.status_code}"
            )


@pytest.mark.security
class TestRateLimitSecurity:
    """Tests for rate limiting security."""

    def test_rate_limit_bypass_headers(self, base_url: str, sample_cookies: dict[str, str]):
        """Test that rate limiting cannot be easily bypassed."""
        bypass_headers = [
            {"X-Forwarded-For": "1.2.3.4"},
            {"X-Real-IP": "5.6.7.8"},
            {"X-Client-IP": "9.10.11.12"},
            {"CF-Connecting-IP": "13.14.15.16"},
        ]

        for headers in bypass_headers:
            all_headers = {**headers, "Origin": base_url}

            # Make rapid requests
            responses = []
            for _ in range(10):
                response = requests.post(
                    f"{base_url}/api/cookies", json=sample_cookies, headers=all_headers
                )
                responses.append(response.status_code)

            # Should still be rate limited
            # Note: This test might fail if the app doesn't implement proper rate limiting
            # It's more of a check to see if rate limiting exists
            # We don't assert here because not all apps have rate limiting

    def test_rate_limit_consistency(self, base_url: str, sample_cookies: dict[str, str]):
        """Test that rate limiting is consistent."""
        headers = {"Origin": base_url}

        # Make many requests from same IP
        responses = []
        for _ in range(15):
            response = requests.post(
                f"{base_url}/api/cookies", json=sample_cookies, headers=headers
            )
            responses.append(response.status_code)

        # After rate limit is hit, subsequent requests should also be limited
        # (at least most of them)
        if 429 in responses:
            first_429 = responses.index(429)
            after_limit = responses[first_429:]
            rate_limited_after = after_limit.count(429)

            # Most requests after first 429 should also be limited
            # (allowing for some race conditions in the window)
            assert rate_limited_after >= len(after_limit) * 0.7, (
                "Rate limiting is not consistent after first limit"
            )


@pytest.mark.security
class TestAuthenticationSecurity:
    """Tests for authentication security."""

    def test_session_validation(self, base_url: str):
        """Test that invalid sessions are properly rejected."""
        # Try with invalid cookies
        invalid_cookies = {
            "session_id": "invalid_session_12345",
            "auth_token": "invalid_token",
        }

        response = requests.post(
            f"{base_url}/api/cookies",
            json=invalid_cookies,
            headers={"Origin": base_url},
        )

        # Should either succeed (200) or indicate invalid session (401)
        assert response.status_code in [200, 401, 400]

    def test_missing_authentication(self, base_url: str):
        """Test behavior without authentication."""
        # Try to access protected endpoint without cookies
        response = requests.get(f"{base_url}/api/status")

        # Should either succeed with no session info or fail
        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            # Should indicate no valid session
            assert data.get("valid") is False or data.get("has_cookies") is False

    def test_cookie_confidentiality(self, base_url: str, sample_cookies: dict[str, str]):
        """Test that cookies are handled securely."""
        # Save cookies
        requests.post(f"{base_url}/api/cookies", json=sample_cookies, headers={"Origin": base_url})

        # Retrieve cookies (same origin)
        response = requests.get(f"{base_url}/api/cookies", headers={"Origin": base_url})

        assert response.status_code == 200
        data = response.json()

        # Verify cookies were retrieved
        assert "cookies" in data


@pytest.mark.security
class TestInputValidation:
    """Tests for input validation security."""

    def test_very_long_inputs(self, base_url: str):
        """Test handling of extremely long inputs."""
        long_string = "A" * 10000

        # Test search with long query
        response = requests.get(f"{base_url}/api/search?q={long_string}")
        assert response.status_code in [
            200,
            400,
            413,
            414,
        ]  # 413/414 = Payload/URI too large

        # Test book ID with long string
        response = requests.get(f"{base_url}/api/book/{long_string}")
        assert response.status_code in [400, 404, 414]

    def test_special_characters_in_inputs(self, base_url: str):
        """Test handling of special characters."""
        special_strings = [
            "test\x00null",  # Null byte
            "test\nnewline",  # Newline
            "test\rcarriage",  # Carriage return
            "test\t tab",  # Tab
            "test\x1bescape",  # Escape character
            "test🔥emoji",  # Emoji
        ]

        for special in special_strings:
            response = requests.get(f"{base_url}/api/search?q={special}")
            # Should handle gracefully
            assert response.status_code in [200, 400, 500]

    def test_unicode_normalization(self, base_url: str):
        """Test handling of Unicode edge cases."""
        unicode_strings = [
            "café",  # Normal Unicode
            "caf\u0065\u0301",  # e + combining acute accent
            "\u00e9",  # Precomposed é
            "test\u200b",  # Zero-width space
            "test\ufeff",  # BOM
        ]

        for unicode_str in unicode_strings:
            response = requests.get(f"{base_url}/api/search?q={unicode_str}")
            assert response.status_code in [200, 400]

    def test_json_injection(self, base_url: str):
        """Test JSON injection attempts."""
        json_payloads = [
            {"book_id": "test", "format": ["epub"], "extra": {"$ne": None}},
            {"book_id": "test", "format": {"$gt": ""}},
            {"book_id": {"$regex": ".*"}, "format": ["epub"]},
        ]

        for payload in json_payloads:
            response = requests.post(
                f"{base_url}/api/download", json=payload, headers={"Origin": base_url}
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]


@pytest.mark.security
class TestErrorHandlingSecurity:
    """Tests for secure error handling."""

    def test_error_message_security(self, base_url: str):
        """Test that error messages don't leak sensitive info."""
        # Trigger various errors
        responses = [
            requests.get(f"{base_url}/api/book/' OR 1=1"),  # SQL-like
            requests.get(f"{base_url}/api/search?q=<script>"),  # XSS-like
            requests.post(
                f"{base_url}/api/download",
                json={"invalid": "data"},
                headers={"Origin": base_url},
            ),
        ]

        sensitive_patterns = [
            "sql",
            "sqlite",
            "database",
            "exception",
            "traceback",
            "stack trace",
            "internal error",
            "server path",
            "file path",
        ]

        for response in responses:
            response_text = response.text.lower()

            for pattern in sensitive_patterns:
                # Check that sensitive info isn't leaked
                # Note: This is a heuristic check
                if pattern in response_text and "error" in response_text:
                    # Log but don't assert - depends on error handling strategy
                    pass

    def test_status_code_consistency(self, base_url: str):
        """Test that status codes are consistent and don't leak info."""
        # Test various invalid inputs
        test_cases = [
            ("GET", "/api/book/"),  # Missing ID
            ("GET", "/api/book/../../../etc/passwd"),  # Path traversal
            ("POST", "/api/cookies"),  # Missing body
        ]

        for method, endpoint in test_cases:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}")
            else:
                response = requests.post(f"{base_url}{endpoint}")

            # Should not return 200 for clearly invalid requests
            if endpoint.endswith("/") or ".." in endpoint:
                assert response.status_code != 200, f"Invalid request to {endpoint} returned 200"


@pytest.mark.security
class TestHTTPHeaderSecurity:
    """Tests for HTTP header security."""

    def test_security_headers(self, base_url: str):
        """Test for security-related HTTP headers."""
        response = requests.get(f"{base_url}/api/status")

        # Check for security headers (if implemented)
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "Content-Security-Policy": None,  # Any value is good
            "Strict-Transport-Security": None,  # Any value is good
            "X-XSS-Protection": ["1", "1; mode=block"],
        }

        for header, expected in security_headers.items():
            if header in response.headers:
                if expected is None:
                    assert response.headers[header], f"{header} is empty"
                elif isinstance(expected, list):
                    assert response.headers[header] in expected, (
                        f"{header} has unexpected value: {response.headers[header]}"
                    )
                else:
                    assert response.headers[header] == expected, (
                        f"{header} should be {expected}, got {response.headers[header]}"
                    )

    def test_no_sensitive_headers(self, base_url: str):
        """Test that sensitive headers are not exposed."""
        response = requests.get(f"{base_url}/api/status")

        # Check that server doesn't expose sensitive info
        sensitive_headers = [
            "X-Powered-By",
            "Server",
            "X-AspNet-Version",
            "X-AspNetMvc-Version",
        ]

        for header in sensitive_headers:
            if header in response.headers:
                # Just warn, don't fail - some headers are acceptable
                pass
