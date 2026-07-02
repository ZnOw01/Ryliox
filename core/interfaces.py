"""Interfaces (Protocols) for Dependency Inversion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.dto import (
        DownloadErrorDTO,
        DownloadJobDTO,
        DownloadProgressDTO,
        DownloadResultDTO,
    )


@runtime_checkable
class IDownloadJobRepository(Protocol):
    """Protocol for DownloadJob persistence operations."""

    def get_by_id(self, job_id: str) -> dict[str, Any] | None: ...

    def get_latest(self) -> dict[str, Any] | None: ...

    def get_latest_cancellable(self) -> str | None: ...

    def list_all(
        self, limit: int | None = None, status_filter: str | None = None
    ) -> list[dict[str, Any]]: ...

    def save(self, job_dto: DownloadJobDTO) -> dict[str, Any]: ...

    def update(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None: ...

    def delete(self, job_id: str) -> bool: ...

    def claim_next_queued(self) -> DownloadJobDTO | None: ...

    def is_cancel_requested(self, job_id: str) -> bool: ...

    def requeue_inflight(self) -> None: ...

    def prune_terminal(self) -> None: ...

    def request_cancel(self, job_id: str) -> tuple[str, dict[str, Any] | None]: ...

    def update_progress(self, job_id: str, progress: DownloadProgressDTO) -> bool: ...

    def mark_completed(self, job_id: str, result: DownloadResultDTO) -> bool: ...

    def mark_failed(
        self,
        job_id: str,
        error_dto: DownloadErrorDTO,
        status: str = "error",
    ) -> bool: ...

    def close(self) -> None: ...


@runtime_checkable
class IUnitOfWork(Protocol):
    """Protocol for atomic transactions."""

    def __enter__(self) -> IUnitOfWork:
        """Enter the runtime context."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Exit the runtime context."""
        ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


@runtime_checkable
class IProgressTracker(Protocol):
    """Protocol for decoupled progress tracking."""

    def update_progress(self, job_id: str, progress: Any) -> None: ...

    def mark_completed(self, job_id: str, result: Any) -> None: ...

    def mark_failed(
        self,
        job_id: str,
        status: str,
        error: str,
        code: str,
        details: dict[str, Any] | None = None,
        trace_log: str | None = None,
    ) -> None: ...


@runtime_checkable
class IJobMapper(Protocol):
    """Protocol for DTO <-> DB mapping."""

    def to_entity(self, row: Any) -> dict[str, Any]: ...

    def to_db(self, entity: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class IDownloadQueueService(Protocol):
    """Protocol for download queue service."""

    def start(self) -> None: ...

    def stop(self, timeout_seconds: float = 5.0) -> None: ...

    def enqueue(
        self,
        *,
        book_id: str,
        output_dir: Any,
        formats: list[str],
        selected_chapters: list[int] | None,
        skip_images: bool,
    ) -> dict[str, Any]: ...

    def get_progress(self, job_id: str | None = None) -> dict[str, Any]: ...

    def cancel(self, job_id: str | None = None) -> tuple[bool, str]: ...

    def get_progress_version(self) -> int: ...

    def wait_for_progress_change(self, previous_version: int, timeout_seconds: float) -> int: ...
