"""Tests for advanced security features."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from web.dependencies import (
    ForbiddenOriginError,
    get_download_queue,
    get_kernel,
    get_request_id,
    get_session_store,
    require_same_origin,
)
from web.server import create_app


class TestSecurityMiddleware:
    """Test cases for security middleware."""

    def test_request_id_middleware_adds_header(self):
        """Test that requests receive an X-Request-ID header."""
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/status")

        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"]

    def test_request_id_middleware_preserves_existing_header(self):
        """Test that a caller-provided request ID is preserved."""
        app = create_app()
        with TestClient(app) as client:
            response = client.get(
                "/api/status",
                headers={"X-Request-ID": "external-request-id"},
            )

        assert response.headers["x-request-id"] == "external-request-id"

    def test_security_headers_present(self):
        """Test that security headers are added to responses."""
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/status")

        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-xss-protection"] == "1; mode=block"
        assert "referrer-policy" in response.headers
        assert "permissions-policy" in response.headers

    def test_csp_header_present(self):
        """Test that Content-Security-Policy header is present."""
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/status")

        assert "content-security-policy" in response.headers
        assert "default-src 'self'" in response.headers["content-security-policy"]

    def test_request_size_limit_too_large(self):
        """Test that requests exceeding size limit are rejected."""
        app = create_app()
        with TestClient(app) as client:
            large_payload = "x" * (11 * 1024 * 1024)
            response = client.post(
                "/api/download",
                json={"book_id": "test", "format": "pdf"},
                headers={"Content-Length": str(len(large_payload))},
            )

        assert response.status_code == 413
        assert response.json()["code"] == "request_too_large"


class TestDependencyInjection:
    """Test cases for dependency providers."""

    def test_get_kernel_yields_kernel(self):
        """Test that get_kernel dependency yields the kernel properly."""
        mock_request = MagicMock()
        mock_request.app.state.kernel = MagicMock()

        gen = get_kernel(mock_request)
        kernel = next(gen)

        assert kernel is mock_request.app.state.kernel
        gen.close()

    def test_get_kernel_re_raises_http_exception(self):
        """Test that get_kernel propagates HTTPException unchanged."""
        mock_request = MagicMock()
        mock_request.app.state.kernel = MagicMock()

        gen = get_kernel(mock_request)
        next(gen)
        with pytest.raises(HTTPException) as exc_info:
            gen.throw(HTTPException(status_code=404, detail="missing"))

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "missing"

    def test_get_session_store_yields_store(self):
        """Test that get_session_store dependency yields the session store."""
        mock_request = MagicMock()
        mock_request.app.state.session_store = MagicMock()

        gen = get_session_store(mock_request)
        store = next(gen)
        assert store is mock_request.app.state.session_store
        gen.close()

    def test_get_session_store_wraps_unexpected_errors(self):
        """Test that get_session_store converts unexpected errors to 500s."""
        mock_request = MagicMock()
        mock_request.app.state.session_store = MagicMock()

        gen = get_session_store(mock_request)
        next(gen)
        with pytest.raises(HTTPException) as exc_info:
            gen.throw(RuntimeError("boom"))

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error in session service"

    def test_get_download_queue_yields_queue(self):
        """Test that get_download_queue dependency yields the download queue."""
        mock_request = MagicMock()
        mock_request.app.state.download_queue = MagicMock()

        gen = get_download_queue(mock_request)
        queue = next(gen)

        assert queue is mock_request.app.state.download_queue
        gen.close()

    def test_get_request_id_from_state(self):
        """Test that get_request_id returns the request ID from state."""
        mock_request = SimpleNamespace(state=SimpleNamespace(request_id="test-request-id-123"))

        request_id = get_request_id(mock_request)

        assert request_id == "test-request-id-123"

    def test_get_request_id_unknown(self):
        """Test that get_request_id returns 'unknown' when no ID in state."""
        mock_request = SimpleNamespace(state=SimpleNamespace())

        request_id = get_request_id(mock_request)

        assert request_id == "unknown"


class TestBackgroundTasks:
    """Test cases for background tasks."""

    @pytest.mark.asyncio
    async def test_cleanup_old_files_task(self, tmp_path):
        """Test that cleanup_old_files_task removes old files."""
        import time

        from web.routes.downloads import cleanup_old_files_task

        # Create test files
        old_file = tmp_path / "test.pdf"
        old_file.write_text("old content")

        # Set modification time to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(old_file, (old_time, old_time))

        # Run cleanup task
        await cleanup_old_files_task(tmp_path, max_age_hours=24)

        # File should be removed
        assert not old_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_preserves_new_files(self, tmp_path):
        """Test that cleanup_old_files_task preserves recent files."""
        from web.routes.downloads import cleanup_old_files_task

        # Create recent test file
        new_file = tmp_path / "test.epub"
        new_file.write_text("new content")

        # Run cleanup task
        await cleanup_old_files_task(tmp_path, max_age_hours=24)

        # File should still exist
        assert new_file.exists()


class TestSSEDisconnection:
    """Test cases for SSE disconnection handling."""

    @pytest.mark.asyncio
    async def test_progress_stream_handles_disconnection(self):
        """Test that progress_stream handles client disconnection gracefully."""
        from web.routes.downloads import progress_stream

        mock_request = MagicMock()
        mock_request.is_disconnected = MagicMock(return_value=True)
        mock_request.state.request_id = "test-id"

        mock_queue = MagicMock()
        mock_queue.get_progress.return_value = {"job_id": "test-job", "status": "idle"}
        mock_queue.get_progress_version.return_value = 1
        mock_queue.wait_for_progress_change.return_value = 2

        response = await progress_stream(
            request=mock_request,
            job_id="test-job",
            download_queue=mock_queue,
            request_id="test-id",
        )

        assert response is not None
        assert "x-request-id" in response.headers


class TestSameOriginGuard:
    """Test cases for same-origin request guarding."""

    def test_forbidden_origin_error_creation(self):
        """Test ForbiddenOriginError creation."""
        error = ForbiddenOriginError("test_operation")

        assert str(error) == "Cross-origin request blocked for 'test_operation'."
        assert error.http_status == 403

    def test_require_same_origin_returns_callable(self):
        """Test that require_same_origin returns a callable."""
        guard = require_same_origin("test")

        assert callable(guard)

    def test_require_same_origin_blocks_cross_origin_request(self):
        """Test that same-origin protection blocks mismatched origins."""
        guard = require_same_origin("save_cookies")
        request = MagicMock()
        request.method = "POST"
        request.headers = {
            "origin": "https://evil.example",
            "host": "localhost:8000",
        }
        request.url.scheme = "http"

        with pytest.raises(ForbiddenOriginError):
            guard(request)

    def test_require_same_origin_allows_matching_origin(self):
        """Test that same-origin protection allows matching origins."""
        guard = require_same_origin("save_cookies")
        request = MagicMock()
        request.method = "POST"
        request.headers = {
            "origin": "http://localhost:8000",
            "host": "localhost:8000",
        }
        request.url.scheme = "http"

        assert guard(request) is None
