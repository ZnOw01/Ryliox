"""Service layer for download queue business logic."""

from __future__ import annotations

import asyncio
import contextlib
import errno
import logging
import threading
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import fcntl
except ImportError:  # pragma: no cover - fcntl is available on Linux deployments
    fcntl = None  # type: ignore[assignment]

from core.audit import AuditEventType, audit_download
from core.contracts import DownloadCancelledError
from core.dto import (
    DownloadErrorDTO,
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
)
from core.metrics import metrics
from core.repository import (
    DEFAULT_TERMINAL_JOB_RETENTION,
    TERMINAL_STATES,
    DownloadJobRepository,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.interfaces import IDownloadJobRepository
    from plugins.downloader import DownloadProgress, DownloadResult

logger = logging.getLogger(__name__)

# Constants
DEFAULT_QUEUE_POLL_INTERVAL_SECONDS = 0.5
MIN_QUEUE_POLL_INTERVAL_SECONDS = 0.1
WORKER_ERROR_LOG_COOLDOWN_SECONDS = 60.0


class QueueCapacityError(RuntimeError):
    """Raised when the configured pending-job bound has been reached."""


class _ProcessWorkerLock:
    """Non-blocking process lock held for the lifetime of a queue worker."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._handle: Any | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        if fcntl is None:
            raise RuntimeError("Cannot verify the download worker singleton: fcntl is unavailable")

        try:
            handle = self._db_path.open("a+")
        except OSError as exc:
            raise RuntimeError(f"Cannot open the download worker lock for {self._db_path}") from exc

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            with contextlib.suppress(OSError):
                handle.close()
            raise RuntimeError(
                f"A download queue worker is already active for {self._db_path}"
            ) from exc
        except OSError as exc:
            with contextlib.suppress(OSError):
                handle.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise RuntimeError(
                    f"A download queue worker is already active for {self._db_path}"
                ) from exc
            raise RuntimeError(
                f"Cannot acquire the download worker lock for {self._db_path}"
            ) from exc

        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return

        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            logger.warning("Failed to explicitly release the worker lock", exc_info=True)
        finally:
            with contextlib.suppress(OSError):
                handle.close()


def _repository_db_path(repository: object) -> Path | None:
    """Return a concrete repository path, if the adapter exposes one."""
    try:
        value = getattr(repository, "db_path", None)
    except Exception:
        return None
    if value is None or isinstance(value, bool):
        return None
    try:
        return Path(value).resolve()
    except (OSError, TypeError, ValueError):
        return None


class DownloadQueueService:
    """Service for managing the download queue.

    Repositories exposing ``db_path`` are protected by a process-wide worker
    lock. Compatibility repositories without that attribute remain usable, but
    their singleton worker cannot be verified.
    """

    def __init__(
        self,
        *,
        kernel_factory: Callable[[], Awaitable[Any]],
        repository: IDownloadJobRepository | None = None,
        db_path: Path | None = None,
        error_log_dir: Path,
        poll_interval_seconds: float = DEFAULT_QUEUE_POLL_INTERVAL_SECONDS,
        terminal_job_retention: int = DEFAULT_TERMINAL_JOB_RETENTION,
        max_queued_jobs: int = 50,
        download_timeout_seconds: float = 600.0,
    ):
        """Initialize the service."""
        self._kernel_factory = kernel_factory
        self._error_log_dir = Path(error_log_dir)
        self._poll_interval_seconds = max(
            MIN_QUEUE_POLL_INTERVAL_SECONDS, float(poll_interval_seconds)
        )
        self._max_queued_jobs = int(max_queued_jobs)
        if self._max_queued_jobs <= 0:
            raise ValueError("max_queued_jobs must be greater than zero")
        self._download_timeout_seconds = max(1.0, float(download_timeout_seconds))

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
        self._progress_lock = threading.Lock()
        self._async_waiters: set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()
        self._progress_version = 0
        self._stop_event = threading.Event()

        # Worker state
        self._active_job_id: str | None = None
        self._active_cancel_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._last_progress_log: dict[str, tuple[str, int, str]] = {}
        repository_db_path = _repository_db_path(self._repository)
        self._worker_lock = (
            _ProcessWorkerLock(repository_db_path) if repository_db_path is not None else None
        )
        if self._worker_lock is None:
            logger.warning(
                "Repository does not expose db_path; the download worker singleton "
                "cannot be verified for this service"
            )

        # Error deduplication
        self._last_worker_error_signature: str | None = None
        self._last_worker_error_logged_at: float = 0.0
        self._worker_error_log_cooldown_seconds = WORKER_ERROR_LOG_COOLDOWN_SECONDS

        self._sync_metrics()

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

            try:
                if self._worker_lock is not None:
                    self._worker_lock.acquire()

                requeue_inflight = getattr(self._repository, "requeue_inflight", None)
                if callable(requeue_inflight):
                    requeue_inflight()

                self._stop_event.clear()
                self._worker = threading.Thread(
                    target=self._worker_loop,
                    name="download-queue-worker",
                    daemon=True,
                )
                self._worker.start()
            except Exception:
                self._stop_event.set()
                self._worker = None
                if self._worker_lock is not None:
                    self._worker_lock.release()
                raise
            logger.info("Download queue worker started")

    def stop(self, timeout_seconds: float = 5.0) -> bool:
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

        if worker and worker.is_alive():
            worker.join(timeout=max(MIN_QUEUE_POLL_INTERVAL_SECONDS, timeout_seconds))
        if worker and worker.is_alive():
            logger.critical(
                "Download queue worker did not stop before timeout; repository left open"
            )
            return False
        try:
            with contextlib.suppress(Exception):
                self._repository.close()
        finally:
            if self._worker_lock is not None:
                self._worker_lock.release()
            with self._state_lock:
                self._worker = None
        logger.info("Download queue worker stopped")
        return True

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

        snapshot = self._enqueue_if_capacity(job_dto)
        if snapshot is None:
            self._sync_metrics()
            raise QueueCapacityError("Download queue is full")

        metrics.record_download_started(",".join(job_dto.formats))
        self._wake_event.set()
        self._notify_progress_change()

        logger.info("Enqueued job %s for book %s", job_dto.job_id[:8], book_id)
        self._sync_metrics()
        audit_download(AuditEventType.DOWNLOAD_STARTED, book_id, job_dto.job_id)
        return snapshot

    def _enqueue_if_capacity(self, job_dto: DownloadJobDTO) -> dict[str, Any] | None:
        """Admit the job atomically; return its snapshot or None when full."""
        return self._repository.enqueue_if_capacity(job_dto, self._max_queued_jobs)

    def _repository_count(self, method_name: str) -> int | None:
        method = getattr(self._repository, method_name, None)
        if not callable(method):
            return None
        try:
            value = method()
        except Exception:
            logger.debug("Repository does not support %s", method_name, exc_info=True)
            return None
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    def _sync_metrics(self) -> None:
        """Synchronize queue gauges with durable repository state."""
        queued_count = self._repository_count("count_queued")
        active_count = self._repository_count("count_active")
        if queued_count is not None:
            metrics.set_queue_size(queued_count)
        if active_count is not None:
            metrics.set_active_downloads(active_count)

    def get_progress(self, job_id: str | None = None) -> dict[str, Any]:
        """Get progress for a specific job or the most recent one."""
        if job_id:
            snapshot = self._repository.get_by_id(job_id)
            return snapshot or {}

        latest = self._repository.get_latest()
        return latest or {}

    def cancel(self, job_id: str | None = None) -> tuple[bool, str]:
        """Cancel a download job."""
        try:
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

            if outcome == "too_late":
                return False, "Download is finalizing"

            if outcome == "cancelled":
                metrics.record_download_cancelled()
                self._notify_progress_change()
                return True, "Download cancelled"

            if is_active and cancel_event is not None:
                cancel_event.set()

            self._notify_progress_change()
            return True, "Cancel requested"
        finally:
            self._sync_metrics()

    def get_progress_version(self) -> int:
        """Return monotonic progress version for SSE waiters."""
        with self._progress_lock:
            return self._progress_version

    async def wait_for_progress_change_async(
        self, previous_version: int, timeout_seconds: float
    ) -> int:
        """Await a progress notification without occupying a worker thread."""
        loop = asyncio.get_running_loop()
        event = asyncio.Event()
        waiter = (loop, event)
        with self._progress_lock:
            if self._progress_version != previous_version:
                return self._progress_version
            self._async_waiters.add(waiter)
        try:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(event.wait(), timeout=max(0.0, timeout_seconds))
        finally:
            with self._progress_lock:
                self._async_waiters.discard(waiter)
        return self.get_progress_version()

    def _notify_progress_change(self) -> None:
        """Notify all waiters of progress change."""
        with self._progress_lock:
            self._progress_version += 1
            waiters = tuple(self._async_waiters)
        for loop, event in waiters:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(event.set)

    def _worker_loop(self) -> None:
        """Main worker daemon loop."""
        while not self._stop_event.is_set():
            job_dto: DownloadJobDTO | None = None

            try:
                # Cheap read-only pre-check: skip the write transaction and
                # prune in claim_next_queued while the queue is empty. The
                # wake event makes enqueues visible immediately.
                if self._repository.has_queued_jobs():
                    job_dto = self._repository.claim_next_queued()
                    self._sync_metrics()

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
                marked = self._repository.mark_failed(
                    job_dto.job_id,
                    error_dto,
                    status="error",
                )
                if marked:
                    metrics.record_download_failed(",".join(job_dto.formats), type(exc).__name__)
                self._notify_progress_change()
            except Exception:
                logger.exception("Failed to mark job as failed")
        self._sync_metrics()

    def _run_job(self, job: DownloadJobDTO) -> None:
        """Execute a download job with proper event loop handling."""
        cancel_event = threading.Event()
        started_at = time.monotonic()

        with self._state_lock:
            self._active_job_id = job.job_id
            self._active_cancel_event = cancel_event

        if self._repository.is_cancel_requested(job.job_id):
            cancel_event.set()

        def report_progress(progress: DownloadProgress) -> None:
            """Update progress in repository."""
            if self._check_and_signal_cancel(job.job_id, cancel_event):
                raise DownloadCancelledError("Download cancelled by user")

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
                        job_id=job.job_id,
                    )
                finally:
                    if entered_kernel:
                        with contextlib.suppress(Exception):
                            await kernel.__aexit__(None, None, None)

            with runner:
                # The whole pipeline runs under one overall timeout
                # (self._download_timeout_seconds); individual HTTP requests
                # have shorter timeouts and the user can also cancel via the
                # UI. On expiry asyncio.TimeoutError propagates and the job
                # is marked failed.
                result = runner.run(
                    asyncio.wait_for(run_download(), timeout=self._download_timeout_seconds)
                )

            if self._check_and_signal_cancel(job.job_id, cancel_event):
                raise DownloadCancelledError("Download cancelled by user")

            pdf_paths = result.files.get("pdf")

            result_dto = DownloadResultDTO(
                book_id=result.book_id,
                title=result.title,
                epub_path=result.files.get("epub"),
                pdf_paths=pdf_paths,
                chapters_count=result.chapters_count,
            )

            if not self._repository.mark_completed(job.job_id, result_dto):
                if self._is_terminal_job(job.job_id):
                    logger.info(
                        "Job %s reached a terminal state before completion was persisted",
                        job.job_id[:8],
                    )
                    return
                raise RuntimeError("Download job could not transition to completed")
            metrics.record_download_completed(",".join(job.formats), time.monotonic() - started_at)
            self._notify_progress_change()
            logger.info("Job %s completed successfully", job.job_id[:8])
            audit_download(AuditEventType.DOWNLOAD_COMPLETED, job.book_id, job.job_id)

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
            self._sync_metrics()

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
        already_terminal = self._is_terminal_job(job.job_id)
        cancelled = isinstance(exc, DownloadCancelledError)

        if already_terminal:
            logger.info("Job %s is already terminal; preserving its state", job.job_id[:8])
        elif cancelled or self._check_and_signal_cancel(job.job_id, cancel_event):
            error_dto = DownloadErrorDTO(
                error=message or "Download cancelled by user",
                code="download_cancelled",
                details=None,
                trace_log=trace_log,
            )
            if self._repository.mark_failed(
                job.job_id,
                error_dto,
                status="cancelled",
            ):
                metrics.record_download_cancelled()
            logger.info("Job %s cancelled by user", job.job_id[:8])
        else:
            error_dto = DownloadErrorDTO(
                error=message or "Download failed",
                code="download_failed",
                details={"trace_log": trace_log} if trace_log else None,
                trace_log=trace_log,
            )
            if self._repository.mark_failed(
                job.job_id,
                error_dto,
                status="error",
            ):
                metrics.record_download_failed(",".join(job.formats), type(exc).__name__)
            logger.error("Job %s failed: %s", job.job_id[:8], message)

        event_type = (
            AuditEventType.DOWNLOAD_CANCELLED
            if cancel_event.is_set() or cancelled
            else AuditEventType.DOWNLOAD_FAILED
        )
        audit_download(event_type, job.book_id, job.job_id, success=False)

        self._notify_progress_change()
        self._sync_metrics()

    def _is_terminal_job(self, job_id: str) -> bool:
        """Check terminal state before applying a competing failure transition."""
        try:
            snapshot = self._repository.get_by_id(job_id)
        except Exception:
            logger.debug("Could not inspect job %s terminal state", job_id, exc_info=True)
            return False
        return snapshot is not None and snapshot.get("status") in TERMINAL_STATES

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
