"""
Service Layer para la cola de descargas.
Implementa lógica de negocio separada del acceso a datos.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from core.dto import (
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
    DownloadErrorDTO,
)
from core.interfaces import IDownloadJobRepository
from core.repository import DownloadJobRepository
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
    """Contexto inmutable para la ejecución de un job."""

    job_id: str
    cancel_event: threading.Event
    error_log_dir: Path


class DownloadQueueService:
    """
    Service Layer para la cola de descargas.

    Responsabilidades:
    - Orquestar el worker de descargas
    - Manejar eventos y sincronización
    - Logging de errores
    - Coordinar con el repository para persistencia

    Delega al repository:
    - Operaciones CRUD de jobs
    - Tracking de progreso
    - Transacciones
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
    ):
        """
        Inicializa el servicio.

        Args:
            kernel_factory: Factory async para crear kernels aislados por job
            repository: Repository para persistencia (opcional, crea uno por defecto)
            db_path: Path a la base de datos (requerido si no se provee repository)
            error_log_dir: Directorio para logs de error
            poll_interval_seconds: Intervalo de polling del worker
            terminal_job_retention: Máximo de jobs terminales a conservar
        """
        self._kernel_factory = kernel_factory
        self._error_log_dir = Path(error_log_dir)
        self._poll_interval_seconds = max(
            MIN_QUEUE_POLL_INTERVAL_SECONDS, float(poll_interval_seconds)
        )

        # Repository (inyección de dependencias)
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

        # Error deduplication
        self._last_worker_error_signature: str | None = None
        self._last_worker_error_logged_at: float = 0.0
        self._worker_error_log_cooldown_seconds = WORKER_ERROR_LOG_COOLDOWN_SECONDS

        # Requeue jobs on startup
        self._repository.requeue_inflight()

    @property
    def repository(self) -> IDownloadJobRepository:
        """Expone el repository para casos avanzados."""
        return self._repository

    def start(self) -> None:
        """Inicia el worker de la cola."""
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
        """Detiene el worker de la cola."""
        self._stop_event.set()
        self._wake_event.set()
        self._notify_progress_change()

        worker: threading.Thread | None
        active_cancel_event: threading.Event | None

        with self._state_lock:
            worker = self._worker
            active_cancel_event = self._active_cancel_event

        if active_cancel_event is not None:
            active_cancel_event.set()

        if worker and worker.is_alive():
            worker.join(timeout=max(MIN_QUEUE_POLL_INTERVAL_SECONDS, timeout_seconds))

        if worker is None or not worker.is_alive():
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
        """
        Encola un nuevo job de descarga.

        Returns:
            Snapshot del job creado
        """
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

        logger.info(f"Enqueued job {job_dto.job_id[:8]} for book {book_id}")
        return snapshot

    def get_progress(self, job_id: str | None = None) -> dict[str, Any]:
        """
        Obtiene el progreso de un job específico o el más reciente.

        Returns:
            Snapshot del job o dict vacío si no se encuentra
        """
        if job_id:
            snapshot = self._repository.get_by_id(job_id)
            return snapshot or {}

        latest = self._repository.get_latest()
        return latest or {}

    def cancel(self, job_id: str | None = None) -> tuple[bool, str]:
        """
        Cancela un job de descarga.

        Args:
            job_id: ID del job a cancelar (None = más reciente activo)

        Returns:
            Tuple (success: bool, message: str)
        """
        target_job_id = job_id or self._repository.get_latest_cancellable()
        if not target_job_id:
            return False, "No active download"

        outcome, snapshot = self._repository.request_cancel(target_job_id)

        if outcome == "not_found":
            return False, "Job not found"

        if outcome == "already_terminal":
            return False, "No active download"

        if outcome == "cancelled":
            self._notify_progress_change()
            return True, "Download cancelled"

        # Cancel requested para job activo
        with self._state_lock:
            if (
                self._active_job_id == target_job_id
                and self._active_cancel_event is not None
            ):
                self._active_cancel_event.set()

        self._notify_progress_change()
        return True, "Cancel requested"

    def get_progress_version(self) -> int:
        """Retorna versión monotónica del progreso para SSE waiters."""
        with self._progress_condition:
            return self._progress_version

    def wait_for_progress_change(
        self, previous_version: int, timeout_seconds: float
    ) -> int:
        """
        Bloquea hasta que el progreso avance o expire el timeout.

        Args:
            previous_version: Versión contra la que comparar
            timeout_seconds: Tiempo máximo de espera

        Returns:
            Nueva versión del progreso
        """
        timeout = max(0.0, float(timeout_seconds))
        with self._progress_condition:
            if self._progress_version != previous_version:
                return self._progress_version
            self._progress_condition.wait(timeout=timeout)
            return self._progress_version

    def _notify_progress_change(self) -> None:
        """Notifica a todos los waiters de cambio en progreso."""
        with self._progress_condition:
            self._progress_version += 1
            self._progress_condition.notify_all()

    def _worker_loop(self) -> None:
        """Loop principal del worker daemon."""
        while not self._stop_event.is_set():
            job_data: dict[str, Any] | None = None

            try:
                # Claim next job atomically
                job_data = self._repository.claim_next_queued()

                if job_data is None:
                    # No jobs available, wait for next wake signal
                    self._wake_event.wait(self._poll_interval_seconds)
                    self._wake_event.clear()
                    continue

                self._notify_progress_change()

                # Convert dict to DTO for execution
                job_dto = DownloadJobDTO.from_dict(job_data)
                self._run_job(job_dto)

            except Exception as exc:
                self._handle_worker_error(exc, job_data)
                self._wake_event.wait(self._poll_interval_seconds)
                self._wake_event.clear()

    def _handle_worker_error(
        self, exc: Exception, job_data: dict[str, Any] | None
    ) -> None:
        """Maneja errores del worker con deduplicación de logs."""
        now = time.time()
        signature = f"{type(exc).__name__}:{exc}"

        should_log = (
            signature != self._last_worker_error_signature
            or (now - self._last_worker_error_logged_at)
            >= self._worker_error_log_cooldown_seconds
        )

        trace_log: str | None = None
        job_id = job_data.get("job_id") if job_data else "worker"

        if should_log:
            trace_text = traceback.format_exc()
            trace_log = self._write_error_trace(trace_text, job_id)
            self._last_worker_error_signature = signature
            self._last_worker_error_logged_at = now
            logger.exception(f"Worker error in job {job_id}")

        # Mark job as failed if we had one
        if job_data is not None and "job_id" in job_data:
            try:
                error_dto = DownloadErrorDTO(
                    error=str(exc) or "Unexpected worker error",
                    code="download_worker_error",
                    details=None,
                    trace_log=trace_log,
                )
                self._repository.mark_failed(
                    job_data["job_id"],
                    error_dto,
                    status="error",
                )
                self._notify_progress_change()
            except Exception:
                logger.exception("Failed to mark job as failed")

    def _run_job(self, job: DownloadJobDTO) -> None:
        """
        Ejecuta un job de descarga con manejo apropiado del event loop.

        Design rationale:
        - Cada job ejecuta en su propio event loop aislado
        - El kernel se crea fresco para cada job
        - Garantizamos cleanup de recursos en finally blocks
        """
        cancel_event = threading.Event()

        with self._state_lock:
            self._active_job_id = job.job_id
            self._active_cancel_event = cancel_event

        # Check if cancel was already requested before starting
        if self._repository.is_cancel_requested(job.job_id):
            cancel_event.set()

        loop: asyncio.AbstractEventLoop | None = None

        try:
            # Create isolated event loop for this job
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Define the async download coroutine
            async def run_download() -> DownloadResult:
                kernel = await self._kernel_factory()
                downloader = kernel["downloader"]

                def report_progress(progress: DownloadProgress) -> None:
                    """Callback para reportar progreso al repository."""
                    progress_dto = DownloadProgressDTO(
                        status=progress.status,
                        percentage=progress.percentage,
                        message=progress.message or "",
                        eta_seconds=progress.eta_seconds,
                        current_chapter=progress.current_chapter or 0,
                        total_chapters=progress.total_chapters or 0,
                        chapter_title=progress.chapter_title or "",
                    )
                    self._repository.update_progress(job.job_id, progress_dto)
                    self._notify_progress_change()

                try:
                    return await downloader.download(
                        book_id=job.book_id,
                        output_dir=job.output_dir,
                        formats=job.formats,
                        selected_chapters=job.selected_chapters,
                        skip_images=job.skip_images,
                        progress_callback=report_progress,
                        cancel_check=lambda: self._is_cancel_requested(
                            job.job_id, cancel_event
                        ),
                    )
                finally:
                    # CRITICAL: Always close kernel resources
                    try:
                        await kernel.__aexit__(None, None, None)
                    except Exception:
                        pass

            # Execute download and get result
            result = loop.run_until_complete(run_download())

            # Convert result to DTO and mark completed
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

            self._repository.mark_completed(job.job_id, result_dto)
            self._notify_progress_change()
            logger.info(f"Job {job.job_id[:8]} completed successfully")

        except Exception as exc:
            self._handle_job_exception(job, exc, cancel_event)
        finally:
            # Cleanup event loop
            if loop is not None:
                self._cleanup_event_loop(loop)

            with self._state_lock:
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
                    self._active_cancel_event = None

            self._wake_event.set()

    def _handle_job_exception(
        self,
        job: DownloadJobDTO,
        exc: Exception,
        cancel_event: threading.Event,
    ) -> None:
        """Maneja excepciones durante la ejecución de un job."""
        message = str(exc)
        trace_text = traceback.format_exc()
        trace_log = self._write_error_trace(trace_text, job.job_id)

        if (
            self._is_cancel_requested(job.job_id, cancel_event)
            or "cancelled" in message.lower()
        ):
            # Cancelled by user
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
            logger.info(f"Job {job.job_id[:8]} cancelled by user")
        else:
            # Actual error
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
            logger.error(f"Job {job.job_id[:8]} failed: {message}")

        self._notify_progress_change()

    def _cleanup_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Limpia un event loop antes de cerrarlo."""
        try:
            # Cancel remaining tasks
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if tasks:
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()
        except Exception:
            pass

    def _is_cancel_requested(self, job_id: str, cancel_event: threading.Event) -> bool:
        """Verifica si se solicitó cancelación por cualquier mecanismo."""
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
        """Escribe trace de error a archivo."""
        try:
            self._error_log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            log_path = (
                self._error_log_dir / f"download-error-{job_id[:8]}-{timestamp}.log"
            )
            log_path.write_text(trace_text, encoding="utf-8")
            return str(log_path)
        except Exception as exc:
            logger.warning(f"Failed to write error trace: {exc}")
            return None
