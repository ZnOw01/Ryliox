"""Service layer for download queue business logic."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.dto import (
    DownloadErrorDTO,
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
)
from core.repository import DownloadJobRepository

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.interfaces import IDownloadJobRepository
    from plugins.downloader import DownloadProgress, DownloadResult

logger = logging.getLogger(__name__)

# Constants
DEFAULT_QUEUE_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_TERMINAL_JOB_RETENTION = 500
MIN_QUEUE_POLL_INTERVAL_SECONDS = 0.1
WORKER_ERROR_LOG_COOLDOWN_SECONDS = 60.0

TERMINAL_STATES = frozenset(["completed", "error", "cancelled"])


@dataclass(frozen=True)
class JobExecutionContext:
    """Immutable context for job execution."""

    job_id: str
    cancel_event: threading.Event
    error_log_dir: Path


class DownloadQueueService:
    """Service for managing download queue."""

    def __init__(
        self,
        *,
        kernel_factory: Callable[[], Awaitable[Any]],
        repository: IDownloadJobRepository | None = None,
        db_path: Path | None = None,
        error_log_dir: Path,
        poll_interval_seconds: float = DEFAULT_QUEUE_POLL_INTERVAL_SECONDS,
        terminal_job_retention: int = DEFAULT_TERMINAL_JOB_RETENTION,
    ):
        """Initialize the service."""
        self._kernel_factory = kernel_factory
        self._error_log_dir = Path(error_log_dir)
        self._poll_interval_seconds = max(
            MIN_QUEUE_POLL_INTERVAL_SECONDS, float(poll_interval_seconds)
        )

        # Repository
        if repository is not None:
            self._repository = repository
        elif db_path is not None:
            self._repository = DownloadJobRepository(
                db_path=db_path,
                terminal_job_retention=terminal_job_retention,
            )
        else:
            raise ValueError("Either 'repository' or 'db_path' must be provided")

        # Synchronization
        self._state_lock = threading.Lock()
        self._wake_event = threading.Event()
        self._progress_condition = threading.Condition()
        self._progress_version = 0
        self._stop_event = threading.Event()

        # Worker state
        self._active_job_id: str | None = None
        self._active_cancel_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._last_progress_log: dict[str, tuple[str, int, str]] = {}

        # Error deduplication
        self._last_worker_error_signature: str | None = None
        self._last_worker_error_logged_at: float = 0.0
        self._worker_error_log_cooldown_seconds = WORKER_ERROR_LOG_COOLDOWN_SECONDS

        # Requeue jobs on startup
        self._repository.requeue_inflight()

    @property
    def repository(self) -> IDownloadJobRepository:
        """Repository access for advanced use cases."""
        return self._repository

    def start(self) -> None:
        """Start the queue worker."""
        with self._state_lock:
            if self._worker and self._worker.is_alive():
                logger.debug("Worker already running, skipping start")
                return

            self._stop_event.clear()
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="download-queue-worker",
                daemon=True,
            )
            self._worker.start()
            logger.info("Download queue worker started")

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Stop the queue worker."""
        self._stop_event.set()
        self._wake_event.set()
        self._notify_progress_change()

        worker: threading.Thread | None
        active_cancel_event: threading.Event | None

        with self._state_lock:
            worker = self._worker
            active_cancel_event = self._active_cancel_event
            self._active_cancel_event = None

        if active_cancel_event is not None:
            active_cancel_event.set()

        try:
            if worker and worker.is_alive():
                worker.join(timeout=max(MIN_QUEUE_POLL_INTERVAL_SECONDS, timeout_seconds))
        finally:
            with contextlib.suppress(Exception):
                self._repository.close()
            logger.info("Download queue worker stopped")

    def enqueue(
        self,
        *,
        book_id: str,
        output_dir: Path,
        formats: list[str],
        selected_chapters: list[int] | None,
        skip_images: bool,
    ) -> dict[str, Any]:
        """Enqueue a new download job."""
        job_dto = DownloadJobDTO.create(
            book_id=book_id,
            output_dir=output_dir,
            formats=formats,
            selected_chapters=selected_chapters,
            skip_images=skip_images,
        )

        snapshot = self._repository.save(job_dto)
        self._wake_event.set()
        self._notify_progress_change()

        logger.info("Enqueued job %s for book %s", job_dto.job_id[:8], book_id)
        return snapshot

    def get_progress(self, job_id: str | None = None) -> dict[str, Any]:
        """Get progress for a specific job or the most recent one."""
        if job_id:
            snapshot = self._repository.get_by_id(job_id)
            return snapshot or {}

        latest = self._repository.get_latest()
        return latest or {}

    def cancel(self, job_id: str | None = None) -> tuple[bool, str]:
        """Cancel a download job."""
        target_job_id = job_id or self._repository.get_latest_cancellable()
        if not target_job_id:
            return False, "No active download"

        with self._state_lock:
            is_active = self._active_job_id == target_job_id
            cancel_event = self._active_cancel_event

        outcome, _ = self._repository.request_cancel(target_job_id)

        if outcome == "not_found":
            return False, "Job not found"

        if outcome == "already_terminal":
            return False, "No active download"

        if outcome == "cancelled":
            self._notify_progress_change()
            return True, "Download cancelled"

        if is_active and cancel_event is not None:
            cancel_event.set()

        self._notify_progress_change()
        return True, "Cancel requested"

    def get_progress_version(self) -> int:
        """Return monotonic progress version for SSE waiters."""
        with self._progress_condition:
            return self._progress_version

    def wait_for_progress_change(self, previous_version: int, timeout_seconds: float) -> int:
        """Block until progress changes or timeout expires."""
        timeout = max(0.0, float(timeout_seconds))
        with self._progress_condition:
            if self._progress_version != previous_version:
                return self._progress_version
            self._progress_condition.wait(timeout=timeout)
            return self._progress_version

    def _notify_progress_change(self) -> None:
        """Notify all waiters of progress change."""
        with self._progress_condition:
            self._progress_version += 1
            self._progress_condition.notify_all()

    def _worker_loop(self) -> None:
        """Main worker daemon loop."""
        while not self._stop_event.is_set():
            job_dto: DownloadJobDTO | None = None

            try:
                job_dto = self._repository.claim_next_queued()

                if job_dto is None:
                    self._wake_event.wait(self._poll_interval_seconds)
                    self._wake_event.clear()
                    continue

                self._notify_progress_change()
                self._run_job(job_dto)

            except Exception as exc:
                self._handle_worker_error(exc, job_dto)
                self._wake_event.wait(self._poll_interval_seconds)
                self._wake_event.clear()

    def _handle_worker_error(self, exc: Exception, job_dto: DownloadJobDTO | None) -> None:
        """Handle worker errors with log deduplication."""
        now = time.time()
        signature = f"{type(exc).__name__}:{exc}"

        should_log = (
            signature != self._last_worker_error_signature
            or (now - self._last_worker_error_logged_at) >= self._worker_error_log_cooldown_seconds
        )

        trace_log: str | None = None
        job_id = job_dto.job_id if job_dto else "worker"

        if should_log:
            trace_text = traceback.format_exc()
            trace_log = self._write_error_trace(trace_text, job_id)
            self._last_worker_error_signature = signature
            self._last_worker_error_logged_at = now
            logger.exception("Worker error in job %s", job_id)

        if job_dto is not None:
            try:
                error_dto = DownloadErrorDTO(
                    error=str(exc) or "Unexpected worker error",
                    code="download_worker_error",
                    details=None,
                    trace_log=trace_log,
                )
                self._repository.mark_failed(
                    job_dto.job_id,
                    error_dto,
                    status="error",
                )
                self._notify_progress_change()
            except Exception:
                logger.exception("Failed to mark job as failed")

    def _run_job(self, job: DownloadJobDTO) -> None:
        """Execute a download job with proper event loop handling."""
        cancel_event = threading.Event()

        with self._state_lock:
            self._active_job_id = job.job_id
            self._active_cancel_event = cancel_event

        if self._repository.is_cancel_requested(job.job_id):
            cancel_event.set()

        def report_progress(progress: DownloadProgress) -> None:
            """Update progress in repository."""
            self._log_progress_event(job.job_id, progress)
            progress_dto = DownloadProgressDTO(
                status=progress.status,
                percentage=progress.percentage,
                message=progress.message,
                eta_seconds=progress.eta_seconds,
                current_chapter=progress.current_chapter,
                total_chapters=progress.total_chapters,
                chapter_title=progress.chapter_title,
            )
            self._repository.update_progress(job.job_id, progress_dto)
            self._notify_progress_change()

        try:
            runner = asyncio.Runner(loop_factory=asyncio.new_event_loop)

            async def run_download() -> DownloadResult:
                kernel = await self._kernel_factory()
                entered_kernel = False
                if not getattr(kernel, "_entered", False):
                    await kernel.__aenter__()
                    entered_kernel = True
                downloader = kernel["downloader"]

                try:
                    return await downloader.download(
                        book_id=job.book_id,
                        output_dir=job.output_dir,
                        formats=job.formats,
                        selected_chapters=job.selected_chapters,
                        skip_images=job.skip_images,
                        progress_callback=report_progress,
                        cancel_check=lambda: self._check_and_signal_cancel(
                            job.job_id, cancel_event
                        ),
                    )
                finally:
                    if entered_kernel:
                        with contextlib.suppress(Exception):
                            await kernel.__aexit__(None, None, None)

            with runner:
                # ponytail: no overall timeout — individual HTTP requests have
                # their own timeout (30s) and the user can cancel via the UI.
                result = runner.run(run_download())

            if self._check_and_signal_cancel(job.job_id, cancel_event):
                raise RuntimeError("Download cancelled by user")

            if result.files.get("pdf"):
                pdf_paths = result.files["pdf"]
            else:
                pdf_paths = None

            result_dto = DownloadResultDTO(
                book_id=result.book_id,
                title=result.title,
                epub_path=result.files.get("epub"),
                pdf_paths=pdf_paths,
                chapters_count=result.chapters_count,
            )

            if not self._repository.mark_completed(job.job_id, result_dto):
                raise RuntimeError("Download job could not transition to completed")
            self._notify_progress_change()
            logger.info("Job %s completed successfully", job.job_id[:8])

        except Exception as exc:
            self._handle_job_exception(job, exc, cancel_event)
        finally:
            try:
                with self._state_lock:
                    if self._active_job_id == job.job_id:
                        self._active_job_id = None
                        self._active_cancel_event = None
                    self._last_progress_log.pop(job.job_id, None)
            except Exception as cleanup_exc:
                logger.debug("Failed to clear active job state: %s", cleanup_exc)
            with contextlib.suppress(Exception):
                self._wake_event.set()

    def _log_progress_event(self, job_id: str, progress: DownloadProgress) -> None:
        percent = max(0, min(100, int(progress.percentage or 0)))
        message = " ".join(str(progress.message or "").split())
        status = str(progress.status or "running")
        previous = self._last_progress_log.get(job_id)
        should_log = previous is None or previous[0] != status or percent >= previous[1] + 5
        if not should_log and percent not in {0, 100}:
            return
        if previous is not None and previous == (status, percent, message):
            return
        self._last_progress_log[job_id] = (status, percent, message)
        logger.info(
            "download_progress job=%s status=%s percent=%d message=%s",
            job_id[:8],
            status,
            percent,
            message or "-",
        )

    def _handle_job_exception(
        self,
        job: DownloadJobDTO,
        exc: Exception,
        cancel_event: threading.Event,
    ) -> None:
        """Handle exceptions during job execution."""
        message = str(exc)
        trace_text = traceback.format_exc()
        trace_log = self._write_error_trace(trace_text, job.job_id)

        if (
            self._check_and_signal_cancel(job.job_id, cancel_event)
            or "cancelled" in message.lower()
        ):
            error_dto = DownloadErrorDTO(
                error=message or "Download cancelled by user",
                code="download_cancelled",
                details=None,
                trace_log=trace_log,
            )
            self._repository.mark_failed(
                job.job_id,
                error_dto,
                status="cancelled",
            )
            logger.info("Job %s cancelled by user", job.job_id[:8])
        else:
            error_dto = DownloadErrorDTO(
                error=message or "Download failed",
                code="download_failed",
                details={"trace_log": trace_log} if trace_log else None,
                trace_log=trace_log,
            )
            self._repository.mark_failed(
                job.job_id,
                error_dto,
                status="error",
            )
            logger.error("Job %s failed: %s", job.job_id[:8], message)

        self._notify_progress_change()

    def _check_and_signal_cancel(self, job_id: str, cancel_event: threading.Event) -> bool:
        """Check if cancellation was requested via any mechanism."""
        if self._stop_event.is_set():
            cancel_event.set()
            return True
        if cancel_event.is_set():
            return True
        if self._repository.is_cancel_requested(job_id):
            cancel_event.set()
            return True
        return False

    def _write_error_trace(self, trace_text: str, job_id: str) -> str | None:
        """Write error trace to file."""
        try:
            self._error_log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            log_path = self._error_log_dir / f"download-error-{job_id[:8]}-{timestamp}.log"
            log_path.write_text(trace_text, encoding="utf-8")
            return str(log_path)
        except Exception as exc:
            logger.warning("Failed to write error trace: %s", exc)
            return None
