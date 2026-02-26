from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace
import uuid

import pytest

from core.download_queue import DownloadQueueService
from plugins.downloader import DownloadProgress

pytestmark = pytest.mark.integration


class BlockingDownloader:
    def __init__(self) -> None:
        self.started = threading.Event()

    async def download(
        self,
        *,
        book_id,
        output_dir,
        formats,
        selected_chapters,
        skip_images,
        progress_callback,
        cancel_check,
    ):
        self.started.set()
        progress_callback(
            DownloadProgress(
                status="processing_chapters",
                percentage=1,
                current_chapter=1,
                total_chapters=100,
                chapter_title="Chapter 1",
                book_id=book_id,
            )
        )
        while True:
            if cancel_check():
                raise Exception("Download cancelled by user")
            await asyncio.sleep(0.02)


class FakeKernel:
    def __init__(self, downloader):
        self._plugins = {"downloader": downloader}
        self.http = SimpleNamespace(close=self._close)

    async def _close(self):
        pass

    def __getitem__(self, name):
        return self._plugins[name]


def _wait_for_status(
    service: DownloadQueueService,
    job_id: str,
    expected: str,
    timeout: float = 3.0,
    interval: float = 0.05,
) -> dict:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = service.get_progress(job_id)
        if snapshot and snapshot.get("status") == expected:
            return snapshot
        time.sleep(interval)
    snapshot = service.get_progress(job_id)
    actual = snapshot.get("status") if snapshot else "None"
    raise TimeoutError(
        f"job {job_id!r} did not reach status {expected!r} in {timeout}s (actual: {actual!r})"
    )


def _workspace_tempdir() -> Path:
    base = Path.cwd() / ".codex_test_runtime_local"
    base.mkdir(parents=True, exist_ok=True)
    temp_path = base / f"tmp-{uuid.uuid4().hex}"
    temp_path.mkdir(parents=True, exist_ok=False)
    return temp_path


def test_download_queue_service_cancel_marks_job_cancelled():
    temp_path = _workspace_tempdir()
    downloader = BlockingDownloader()
    service = DownloadQueueService(
        kernel_factory=lambda: FakeKernel(downloader=downloader),
        db_path=temp_path / "download_jobs.sqlite3",
        error_log_dir=temp_path / "logs",
        poll_interval_seconds=0.05,
    )
    service.start()
    try:
        queued = service.enqueue(
            book_id="demo-book",
            output_dir=temp_path / "output",
            formats=["epub"],
            selected_chapters=None,
            skip_images=False,
        )
        job_id = str(queued["job_id"])
        _wait_for_status(service, job_id, "processing_chapters")
        assert downloader.started.wait(timeout=1.0)
        cancelled, _ = service.cancel(job_id)
        assert cancelled is True
        snapshot = _wait_for_status(service, job_id, "cancelled")
        assert snapshot.get("status") == "cancelled"
    finally:
        service.stop()
        shutil.rmtree(temp_path, ignore_errors=True)
