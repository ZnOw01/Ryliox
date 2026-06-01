"""Integration tests for Downloads API endpoints.

Tests cover:
- Download job queueing
- Progress tracking
- Download cancellation
- SSE progress streaming
- Format validation
- Chapter selection
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
class TestDownloadQueue:
    """Tests for POST /api/download endpoint."""

    def test_download_valid_request(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test queuing a download with valid parameters."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        request_data = {
            "book_id": "9780134685991",
            "format": ["epub"],
            "output_dir": "/tmp/output",
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["book_id"] == "9780134685991"
        assert "job_id" in data
        assert data["queue_position"] is not None

    def test_download_missing_book_id(self, test_client: TestClient):
        """Test download request without book_id."""
        request_data = {
            "format": ["epub"],
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "book_id required" in data.get("error", "")

    def test_download_invalid_format(self, test_client: TestClient, mock_kernel):
        """Test download with invalid format."""
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(
            side_effect=ValueError("Invalid format: xyz")
        )

        request_data = {
            "book_id": "9780134685991",
            "format": ["xyz"],
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid format" in data.get("error", "")

    def test_download_invalid_output_dir(self, test_client: TestClient, mock_kernel):
        """Test download with invalid output directory."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(False, "Directory not writable", None)
        )

        request_data = {
            "book_id": "9780134685991",
            "format": ["epub"],
            "output_dir": "/nonexistent/path",
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "Directory not writable" in data.get("error", "")

    def test_download_chapter_selection(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test download with specific chapters selected."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])
        mock_kernel._plugins["downloader"].supports_chapter_selection = MagicMock(return_value=True)

        request_data = {
            "book_id": "9780134685991",
            "format": ["epub"],
            "chapters": [0, 1, 2],
            "skip_images": True,
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_download_chapters_not_supported_for_format(self, test_client: TestClient, mock_kernel):
        """Test download with chapter selection on unsupported format."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["pdf"])
        mock_kernel._plugins["downloader"].supports_chapter_selection = MagicMock(
            return_value=False
        )

        request_data = {
            "book_id": "9780134685991",
            "format": ["pdf"],
            "chapters": [0, 1],
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "Chapter selection not supported" in data.get("error", "")

    def test_download_cross_origin_blocked(self, test_client: TestClient):
        """Test that cross-origin download requests are blocked."""
        request_data = {
            "book_id": "9780134685991",
            "format": ["epub"],
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "https://malicious-site.com"},
        )

        assert response.status_code == 403

    def test_download_multiple_formats(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test download with multiple output formats."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub", "pdf"])

        request_data = {
            "book_id": "9780134685991",
            "format": ["epub", "pdf"],
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_download_format_string_input(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test download with format as string (legacy support)."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        request_data = {
            "book_id": "9780134685991",
            "format": "epub",  # String instead of list
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200

    def test_download_negative_chapter_indexes(self, test_client: TestClient):
        """Test download with negative chapter indexes."""
        request_data = {
            "book_id": "9780134685991",
            "format": ["epub"],
            "chapters": [-1, 0, 1],  # Negative index
        }

        response = test_client.post(
            "/api/download",
            json=request_data,
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.integration
class TestDownloadProgress:
    """Tests for GET /api/progress endpoint."""

    def test_get_progress_idle(self, test_client: TestClient):
        """Test getting progress when no job is active."""
        response = test_client.get("/api/progress")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["job_id"] == ""

    def test_get_progress_by_job_id(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test getting progress for a specific job."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        # First, queue a download
        download_response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["epub"]},
            headers={"Origin": "http://localhost:8000"},
        )
        job_id = download_response.json()["job_id"]

        # Get progress for the job
        response = test_client.get(f"/api/progress?job_id={job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] in ["queued", "idle"]

    def test_get_progress_invalid_job_id(self, test_client: TestClient):
        """Test getting progress for non-existent job."""
        response = test_client.get("/api/progress?job_id=invalid-job-id-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"


@pytest.mark.integration
class TestDownloadCancel:
    """Tests for POST /api/cancel endpoint."""

    def test_cancel_active_download(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test cancelling an active download."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        # First, queue a download
        download_response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["epub"]},
            headers={"Origin": "http://localhost:8000"},
        )
        job_id = download_response.json()["job_id"]

        # Cancel the download
        response = test_client.post(
            "/api/cancel",
            json={"job_id": job_id},
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Cancel" in data.get("message", "")

    def test_cancel_no_active_job(self, test_client: TestClient):
        """Test cancelling when no job is active."""
        response = test_client.post("/api/cancel", headers={"Origin": "http://localhost:8000"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No active download" in data.get("message", "")

    def test_cancel_invalid_job_id(self, test_client: TestClient):
        """Test cancelling with invalid job ID."""
        response = test_client.post(
            "/api/cancel",
            json={"job_id": "nonexistent-job"},
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data.get("message", "").lower()

    def test_cancel_via_query_param(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test cancelling using job_id query parameter."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        # Queue a download
        download_response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["epub"]},
            headers={"Origin": "http://localhost:8000"},
        )
        job_id = download_response.json()["job_id"]

        # Cancel using query parameter
        response = test_client.post(
            f"/api/cancel?job_id={job_id}", headers={"Origin": "http://localhost:8000"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_cancel_cross_origin_blocked(self, test_client: TestClient):
        """Test that cross-origin cancel requests are blocked."""
        response = test_client.post("/api/cancel", headers={"Origin": "https://malicious-site.com"})

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.rate_limit
class TestDownloadRateLimiting:
    """Tests for rate limiting on download endpoints."""

    def test_download_endpoint_rate_limited(self, test_client: TestClient, mock_kernel):
        """Test that POST /api/download is rate limited."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        headers = {"Origin": "http://localhost:8000"}
        responses = []

        # Make multiple rapid requests
        for _ in range(10):
            response = test_client.post(
                "/api/download",
                json={"book_id": "9780134685991", "format": ["epub"]},
                headers=headers,
            )
            responses.append(response.status_code)

        # At least one should be rate limited
        assert 429 in responses, "Expected at least one rate-limited response"

    def test_progress_endpoint_not_rate_limited(self, test_client: TestClient):
        """Test that GET /api/progress is not rate limited."""
        responses = []

        for _ in range(10):
            response = test_client.get("/api/progress")
            responses.append(response.status_code)

        # All should succeed
        assert all(r == 200 for r in responses), "GET /api/progress should not be rate limited"


@pytest.mark.integration
class TestDownloadProgressStream:
    """Tests for GET /api/progress/stream SSE endpoint."""

    def test_progress_stream_connection(self, test_client: TestClient):
        """Test SSE stream connection."""
        response = test_client.get(
            "/api/progress/stream",
            headers={
                "Origin": "http://localhost:8000",
                "Accept": "text/event-stream",
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"

    def test_progress_stream_cross_origin_blocked(self, test_client: TestClient):
        """Test that cross-origin SSE requests are blocked."""
        response = test_client.get(
            "/api/progress/stream", headers={"Origin": "https://malicious-site.com"}
        )

        assert response.status_code == 403


@pytest.mark.integration
class TestDownloadFormats:
    """Tests for download format handling."""

    def test_download_pdf_format(self, test_client: TestClient, mock_kernel, mock_download_queue):
        """Test download with PDF format."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["pdf"])

        response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["pdf"]},
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200

    def test_download_epub_format(self, test_client: TestClient, mock_kernel, mock_download_queue):
        """Test download with EPUB format."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["epub"]},
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200

    def test_download_combined_formats(
        self, test_client: TestClient, mock_kernel, mock_download_queue
    ):
        """Test download with both EPUB and PDF formats."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, "/tmp/output")
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub", "pdf"])

        response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["epub", "pdf"]},
            headers={"Origin": "http://localhost:8000"},
        )

        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.slow
class TestDownloadWorkflow:
    """End-to-end download workflow tests (may be slow)."""

    def test_queue_download_and_get_progress(
        self, test_client: TestClient, mock_kernel, mock_download_queue, temp_dir
    ):
        """Test full workflow: queue download, check progress, cancel."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, str(temp_dir))
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        # Step 1: Queue download
        download_response = test_client.post(
            "/api/download",
            json={"book_id": "9780134685991", "format": ["epub"]},
            headers={"Origin": "http://localhost:8000"},
        )
        assert download_response.status_code == 200
        job_data = download_response.json()
        job_id = job_data["job_id"]

        # Step 2: Check progress
        progress_response = test_client.get(f"/api/progress?job_id={job_id}")
        assert progress_response.status_code == 200
        progress_data = progress_response.json()
        assert progress_data["job_id"] == job_id

        # Step 3: Cancel
        cancel_response = test_client.post(
            "/api/cancel",
            json={"job_id": job_id},
            headers={"Origin": "http://localhost:8000"},
        )
        assert cancel_response.status_code == 200
        cancel_data = cancel_response.json()
        assert cancel_data["success"] is True

    def test_multiple_downloads_queue_position(
        self, test_client: TestClient, mock_kernel, mock_download_queue, temp_dir
    ):
        """Test that multiple downloads get correct queue positions."""
        mock_kernel._plugins["output"].validate_dir = MagicMock(
            return_value=(True, None, str(temp_dir))
        )
        mock_kernel._plugins["downloader"].parse_formats = MagicMock(return_value=["epub"])

        job_ids = []

        # Queue multiple downloads
        for i in range(3):
            response = test_client.post(
                "/api/download",
                json={"book_id": f"book-{i}", "format": ["epub"]},
                headers={"Origin": "http://localhost:8000"},
            )
            assert response.status_code == 200
            data = response.json()
            job_ids.append(data["job_id"])
            # Queue position should increment
            assert data["queue_position"] == i + 1
