from __future__ import annotations

import asyncio

import pytest
from fastapi.responses import StreamingResponse

from web.routes.downloads import progress_stream

pytestmark = pytest.mark.integration


def test_progress_stream_returns_sse_response(app_client):
    queue = app_client.app.state.download_queue
    response = asyncio.run(progress_stream(job_id=None, download_queue=queue))
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"


def test_progress_endpoint_ignores_zero_chapter_values(app_client, monkeypatch):
    queue = app_client.app.state.download_queue

    def _fake_progress(job_id=None):
        return {
            "job_id": str(job_id or "job-1"),
            "status": "processing_chapters",
            "book_id": "book-1",
            "percentage": 10,
            "current_chapter": 0,
            "total_chapters": 0,
        }

    monkeypatch.setattr(queue, "get_progress", _fake_progress)

    response = app_client.get("/api/progress?job_id=job-1")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "running"
    assert payload["job_id"] == "job-1"
    assert payload.get("current_chapter") is None
    assert payload.get("total_chapters") is None


def test_progress_endpoint_allows_safe_same_origin_get_without_origin_header(app_client):
    response = app_client.get("/api/progress")

    assert response.status_code == 200


def test_progress_endpoint_sanitizes_negative_eta(app_client, monkeypatch):
    queue = app_client.app.state.download_queue

    def _fake_progress(job_id=None):
        return {
            "job_id": str(job_id or "job-1"),
            "status": "processing_chapters",
            "book_id": "book-1",
            "percentage": 25,
            "eta_seconds": -1,
        }

    monkeypatch.setattr(queue, "get_progress", _fake_progress)

    response = app_client.get("/api/progress?job_id=job-1")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "running"
    assert payload.get("eta_seconds") is None


async def _read_first_stream_chunk(response: StreamingResponse) -> str:
    body_iterator = response.body_iterator
    return await anext(body_iterator)


def test_progress_stream_falls_back_on_invalid_snapshot():
    class _FakeQueue:
        def get_progress(self, job_id=None):
            return {
                "job_id": str(job_id or "job-1"),
                "status": "completed",
                "book_id": "book-1",
                "pdf": {"unexpected": "shape"},
            }

        def get_progress_version(self):
            return 0

        def wait_for_progress_change(self, previous_version, timeout_seconds):
            return previous_version + 1

    response = asyncio.run(progress_stream(job_id="job-1", download_queue=_FakeQueue()))
    first_chunk = asyncio.run(_read_first_stream_chunk(response))

    assert "event: progress" in first_chunk
    assert '"status":"error"' in first_chunk
    assert '"code":"invalid_progress_snapshot"' in first_chunk
