from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from core.download_queue import DownloadJobStore, DownloadQueueService
from plugins.downloader import DownloadProgress

pytestmark = pytest.mark.unit


class HangingThread:
    def __init__(self) -> None:
        self.join_calls: list[float] = []

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float) -> None:
        self.join_calls.append(timeout)


def test_stop_raises_when_worker_does_not_exit(tmp_path, monkeypatch):
    service = DownloadQueueService(
        kernel_factory=lambda: SimpleNamespace(http=SimpleNamespace(close=lambda: None)),
        db_path=tmp_path / "download_jobs.sqlite3",
        error_log_dir=tmp_path / "logs",
        poll_interval_seconds=0.05,
    )
    hanging_worker = HangingThread()
    service._worker = hanging_worker  # type: ignore[assignment]
    service._active_cancel_event = threading.Event()

    store_closed = False

    def fake_close() -> None:
        nonlocal store_closed
        store_closed = True

    monkeypatch.setattr(service.store, "close", fake_close)

    with pytest.raises(RuntimeError, match="did not stop"):
        service.stop(timeout_seconds=0.2)

    assert hanging_worker.join_calls == [0.2]
    assert store_closed is False


def test_download_job_store_close_clears_internal_progress_cache(tmp_path):
    store = DownloadJobStore(db_path=tmp_path / "download_jobs.sqlite3")
    store._last_progress_payload["job-1"] = ("running", 10)
    store._last_progress_write_at["job-1"] = 123.0

    store.close()
    assert store._last_progress_payload == {}
    assert store._last_progress_write_at == {}


def test_download_job_store_snapshot_filter_keeps_zero_and_false(tmp_path):
    store = DownloadJobStore(db_path=tmp_path / "download_jobs.sqlite3")

    filtered = store._filter_snapshot_values(
        {
            "percentage": 0,
            "cancel_requested": False,
            "message": None,
        }
    )

    assert filtered == {
        "percentage": 0,
        "cancel_requested": False,
    }


def test_update_progress_returns_false_when_write_is_throttled(tmp_path):
    store = DownloadJobStore(
        db_path=tmp_path / "download_jobs.sqlite3",
        progress_write_interval_seconds=60.0,
    )
    snapshot = store.enqueue_job(
        book_id="demo",
        output_dir=tmp_path / "out",
        formats=["epub"],
        selected_chapters=None,
        skip_images=False,
    )
    job = store.claim_next_queued_job()
    assert job is not None

    wrote = store.update_progress(
        snapshot["job_id"],
        DownloadProgress(status="running", percentage=10, message="a"),
    )
    throttled = store.update_progress(
        snapshot["job_id"],
        DownloadProgress(status="running", percentage=10, message="a"),
    )

    assert wrote is True
    assert throttled is False


def test_mark_cancelled_clears_trace_log(tmp_path):
    store = DownloadJobStore(db_path=tmp_path / "download_jobs.sqlite3")
    snapshot = store.enqueue_job(
        book_id="demo",
        output_dir=tmp_path / "out",
        formats=["epub"],
        selected_chapters=None,
        skip_images=False,
    )
    store.mark_failed(
        job_id=snapshot["job_id"],
        status="error",
        error="boom",
        code="download_failed",
        trace_log="trace.log",
    )

    store.mark_cancelled(job_id=snapshot["job_id"])
    updated = store.get_job_snapshot(snapshot["job_id"])

    assert updated is not None
    assert updated["status"] == "cancelled"
    assert "trace_log" not in updated
