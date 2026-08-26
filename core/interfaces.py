"""Interfaces (Protocols) for Dependency Inversion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from core.dto import (
        DownloadErrorDTO,
        DownloadJobDTO,
        DownloadProgressDTO,
        DownloadResultDTO,
    )


class IDownloadJobRepository(Protocol):
    """Protocol for DownloadJob persistence operations."""

    # Repositories without a path cannot participate in the process singleton
    # lock used by the queue service; those adapters remain compatibility-only.
    @property
    def db_path(self) -> Path: ...

    def get_by_id(self, job_id: str) -> dict[str, Any] | None: ...

    def get_latest(self) -> dict[str, Any] | None: ...

    def get_latest_cancellable(self) -> str | None: ...

    def list_all(
        self, limit: int | None = None, status_filter: str | None = None
    ) -> list[dict[str, Any]]: ...

    def save(self, job_dto: DownloadJobDTO) -> dict[str, Any]: ...

    def enqueue_if_capacity(
        self, job_dto: DownloadJobDTO, max_queued_jobs: int
    ) -> dict[str, Any] | None: ...

    def count_queued(self) -> int: ...

    def count_active(self) -> int: ...

    def has_queued_jobs(self) -> bool: ...

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


class IDownloadQueueService(Protocol):
    """Protocol for download queue service."""

    def start(self) -> None: ...

    def stop(self, timeout_seconds: float = 5.0) -> bool: ...

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

    async def wait_for_progress_change_async(
        self, previous_version: int, timeout_seconds: float
    ) -> int: ...
