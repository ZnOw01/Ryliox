"""
Interfaces (Protocolos) para implementar Dependency Inversion.
Define contratos abstractos que permiten testing con mocks y desacoplamiento.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IDownloadJobRepository(Protocol):
    """Protocolo para operaciones de persistencia de DownloadJobs."""

    def get_by_id(self, job_id: str) -> dict[str, Any] | None:
        """Obtiene un job por su ID."""
        ...

    def get_latest(self) -> dict[str, Any] | None:
        """Obtiene el job más reciente."""
        ...

    def get_latest_cancellable(self) -> str | None:
        """Obtiene el ID del job más reciente que puede cancelarse."""
        ...

    def list_all(
        self, limit: int | None = None, status_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Lista todos los jobs, opcionalmente filtrados."""
        ...

    def save(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Guarda un nuevo job."""
        ...

    def update(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Actualiza un job existente."""
        ...

    def delete(self, job_id: str) -> bool:
        """Elimina un job por su ID."""
        ...

    def claim_next_queued(self) -> dict[str, Any] | None:
        """Reclama el siguiente job en cola (transacción atómica)."""
        ...

    def is_cancel_requested(self, job_id: str) -> bool:
        """Verifica si se solicitó cancelación de un job."""
        ...

    def requeue_inflight(self) -> None:
        """Reencola jobs que quedaron en estado intermedio."""
        ...

    def prune_terminal(self) -> None:
        """Limpia jobs en estados terminales que excedan el límite."""
        ...

    def close(self) -> None:
        """Cierra recursos del repositorio."""
        ...


@runtime_checkable
class IUnitOfWork(Protocol):
    """Protocolo para transacciones atómicas."""

    def __enter__(self) -> IUnitOfWork:
        """Inicia el contexto de transacción."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Finaliza el contexto, hace commit o rollback según corresponda."""
        ...

    def commit(self) -> None:
        """Confirma la transacción."""
        ...

    def rollback(self) -> None:
        """Deshace la transacción."""
        ...


@runtime_checkable
class IProgressTracker(Protocol):
    """Protocolo para tracking de progreso desacoplado."""

    def update_progress(self, job_id: str, progress: Any) -> None:
        """Actualiza el progreso de un job."""
        ...

    def mark_completed(self, job_id: str, result: Any) -> None:
        """Marca un job como completado."""
        ...

    def mark_failed(
        self,
        job_id: str,
        status: str,
        error: str,
        code: str,
        details: dict[str, Any] | None = None,
        trace_log: str | None = None,
    ) -> None:
        """Marca un job como fallido."""
        ...


@runtime_checkable
class IJobMapper(Protocol):
    """Protocolo para mapeo entre DTOs y modelos de base de datos."""

    def to_entity(self, row: Any) -> dict[str, Any]:
        """Convierte una fila de DB a entidad."""
        ...

    def to_db(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Convierte una entidad a formato de DB."""
        ...


@runtime_checkable
class IDownloadQueueService(Protocol):
    """Protocolo para el servicio de cola de descargas."""

    def start(self) -> None:
        """Inicia el worker de la cola."""
        ...

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Detiene el worker de la cola."""
        ...

    def enqueue(
        self,
        *,
        book_id: str,
        output_dir: Any,
        formats: list[str],
        selected_chapters: list[int] | None,
        skip_images: bool,
    ) -> dict[str, Any]:
        """Encola un nuevo job de descarga."""
        ...

    def get_progress(self, job_id: str | None = None) -> dict[str, Any]:
        """Obtiene el progreso de un job o el más reciente."""
        ...

    def cancel(self, job_id: str | None = None) -> tuple[bool, str]:
        """Cancela un job de descarga."""
        ...

    def get_progress_version(self) -> int:
        """Obtiene la versión monotónica del progreso."""
        ...

    def wait_for_progress_change(
        self, previous_version: int, timeout_seconds: float
    ) -> int:
        """Espera cambios en el progreso."""
        ...
