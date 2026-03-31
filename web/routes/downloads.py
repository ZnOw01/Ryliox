"""Download queue and progress routes."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from core.download_queue import DownloadQueueService
from core.kernel import Kernel
from plugins.downloader import DownloaderPlugin
from web.api_utils import ErrorCode, error_response, sse_comment, sse_event
from web.dependencies import (
    get_download_queue,
    get_kernel,
    get_request_id,
    require_same_origin,
)
from web.schemas import (
    CancelRequest,
    CancelResponse,
    DownloadRequest,
    DownloadStartResponse,
    ProgressResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["downloads"])

SSE_HEARTBEAT_INTERVAL_SECONDS: float = 15.0
_PROGRESS_ADAPTER: TypeAdapter[ProgressResponse] = TypeAdapter(ProgressResponse)


def _coerce_str(value: Any) -> str | None:
    """Convierte a str limpio o None si vacío."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_int(value: Any) -> int | None:
    """Convierte a int o None si inválido."""
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _coerce_positive_int(value: Any) -> int | None:
    parsed = _coerce_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _normalize_progress_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Convierte un snapshot crudo del queue en un dict compatible con ProgressResponse."""
    if not isinstance(snapshot, dict):
        return {"status": "idle", "job_id": ""}

    job_id = _coerce_str(snapshot.get("job_id"))
    if not job_id:
        return {"status": "idle", "job_id": ""}

    raw_status = (_coerce_str(snapshot.get("status")) or "").lower()
    book_id = _coerce_str(snapshot.get("book_id"))
    base: dict[str, Any] = {"job_id": job_id, "book_id": book_id}

    if raw_status == "queued":
        queue_position = _coerce_int(snapshot.get("queue_position"))
        return {
            **base,
            "status": "queued",
            "queue_position": max(1, queue_position or 1),
        }

    if raw_status == "completed":
        return {
            **base,
            "status": "completed",
            "title": _coerce_str(snapshot.get("title")),
            "epub": _coerce_str(snapshot.get("epub")),
            "pdf": snapshot.get("pdf"),
        }

    if raw_status in {"error", "cancelled"}:
        fallback = (
            "Download cancelled by user"
            if raw_status == "cancelled"
            else "Download failed"
        )
        return {
            **base,
            "status": "error",
            "error": _coerce_str(snapshot.get("error")) or fallback,
            "code": _coerce_str(snapshot.get("code")),
            "details": (
                snapshot.get("details")
                if isinstance(snapshot.get("details"), dict)
                else None
            ),
            "trace_log": _coerce_str(snapshot.get("trace_log")),
        }

    percentage = max(0, min(100, _coerce_int(snapshot.get("percentage")) or 0))
    return {
        **base,
        "status": "running",
        "percentage": percentage,
        "message": _coerce_str(snapshot.get("message")),
        "eta_seconds": _coerce_int(snapshot.get("eta_seconds")),
        "current_chapter": _coerce_positive_int(snapshot.get("current_chapter")),
        "total_chapters": _coerce_positive_int(snapshot.get("total_chapters")),
        "chapter_title": _coerce_str(snapshot.get("chapter_title")),
        "title": _coerce_str(snapshot.get("title")),
    }


def _progress_payload(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    normalized = _normalize_progress_snapshot(snapshot)
    return _PROGRESS_ADAPTER.validate_python(normalized).model_dump(exclude_none=True)


# Background task functions
async def cleanup_old_files_task(
    output_dir: Path,
    max_age_hours: int = 24,
    file_extensions: tuple[str, ...] = (".pdf", ".epub"),
) -> None:
    """Background task to clean up old generated files.

    This helps prevent disk space issues by removing old files periodically.
    """
    try:
        import asyncio
        from datetime import datetime, timedelta

        if not output_dir.exists():
            logger.debug(
                "Output directory does not exist, skipping cleanup: %s", output_dir
            )
            return

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        removed_count = 0

        for ext in file_extensions:
            for file_path in output_dir.glob(f"*{ext}"):
                try:
                    # Get file modification time
                    stat = await asyncio.to_thread(file_path.stat)
                    mtime = datetime.fromtimestamp(stat.st_mtime)

                    if mtime < cutoff_time:
                        await asyncio.to_thread(file_path.unlink)
                        removed_count += 1
                        logger.info("Cleaned up old file: %s", file_path)
                except OSError as exc:
                    logger.warning("Failed to clean up file %s: %s", file_path, exc)

        if removed_count > 0:
            logger.info("Cleanup completed: removed %d old files", removed_count)
    except Exception as exc:
        logger.exception("Error during file cleanup: %s", exc)


async def notify_progress_task(
    job_id: str,
    download_queue: DownloadQueueService,
    request_id: str,
) -> None:
    """Background task to log progress notifications.

    Useful for tracking long-running downloads across different request contexts.
    """
    try:
        snapshot = download_queue.get_progress(job_id=job_id)
        if snapshot:
            status = snapshot.get("status", "unknown")
            logger.info(
                "[%s] Progress notification for job %s: status=%s",
                request_id,
                job_id,
                status,
            )
    except Exception as exc:
        logger.exception("Error in progress notification task: %s", exc)


@router.get(
    "/progress",
    response_model=ProgressResponse,
    dependencies=[Depends(require_same_origin("get_progress"))],
)
def progress(
    job_id: str | None = Query(default=None),
    download_queue: DownloadQueueService = Depends(get_download_queue),
) -> dict[str, Any]:
    return _progress_payload(download_queue.get_progress(job_id=job_id))


@router.get(
    "/progress/stream",
    dependencies=[Depends(require_same_origin("stream_progress"))],
)
async def progress_stream(
    request: Request,
    job_id: str | None = Query(default=None),
    download_queue: DownloadQueueService = Depends(get_download_queue),
    request_id: str = Depends(get_request_id),
) -> StreamingResponse:
    """Stream download progress with client disconnection handling.

    Implements graceful disconnect detection and proper cleanup.
    """
    logger.info("[%s] Starting SSE stream for job_id=%s", request_id, job_id)

    async def event_stream():
        last_signature: str | None = None
        last_heartbeat_at = time.monotonic()
        progress_version = download_queue.get_progress_version()
        max_iterations = 3600  # 1 hour máximo
        iteration = 0
        disconnect_check_interval = 0.5  # Check disconnect every 500ms
        last_disconnect_check = time.monotonic()

        try:
            while iteration < max_iterations:
                iteration += 1

                # Check for client disconnection periodically
                now = time.monotonic()
                if now - last_disconnect_check >= disconnect_check_interval:
                    last_disconnect_check = now
                    if await request.is_disconnected():
                        logger.info(
                            "[%s] Client disconnected from SSE stream for job_id=%s",
                            request_id,
                            job_id,
                        )
                        break

                snapshot = download_queue.get_progress(job_id=job_id)
                payload = _progress_payload(snapshot)
                signature = json.dumps(payload, sort_keys=True, separators=(",", ":"))

                if signature != last_signature:
                    last_signature = signature
                    yield sse_event("progress", payload)

                # Check for disconnection again before sleeping
                if await request.is_disconnected():
                    logger.info(
                        "[%s] Client disconnected during SSE stream for job_id=%s",
                        request_id,
                        job_id,
                    )
                    break

                now = time.monotonic()
                wait = max(
                    0.1, SSE_HEARTBEAT_INTERVAL_SECONDS - (now - last_heartbeat_at)
                )

                next_version = await asyncio.to_thread(
                    download_queue.wait_for_progress_change,
                    progress_version,
                    wait,
                )
                progress_version = next_version

                now = time.monotonic()
                if now - last_heartbeat_at >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                    last_heartbeat_at = now
                    yield sse_comment("heartbeat")
                    yield sse_event(
                        "heartbeat",
                        {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                    )
        except asyncio.CancelledError:
            logger.debug("[%s] SSE stream cancelled for job_id=%s", request_id, job_id)
            return
        except Exception as exc:
            logger.exception(
                "[%s] Error in SSE stream for job_id=%s: %s", request_id, job_id, exc
            )
            raise
        finally:
            logger.info("[%s] SSE stream ended for job_id=%s", request_id, job_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


@router.post(
    "/cancel",
    response_model=CancelResponse,
    dependencies=[Depends(require_same_origin("cancel_download"))],
)
def cancel_download(
    data: CancelRequest = Body(default_factory=CancelRequest),
    job_id: str | None = Query(default=None),
    download_queue: DownloadQueueService = Depends(get_download_queue),
) -> CancelResponse:
    target_job_id = data.job_id or job_id or None
    cancelled, message = download_queue.cancel(job_id=target_job_id)
    return CancelResponse(success=cancelled, message=message)


@router.post(
    "/download",
    response_model=DownloadStartResponse,
    dependencies=[Depends(require_same_origin("download"))],
)
def download(
    data: DownloadRequest = Body(default_factory=DownloadRequest),
    background_tasks: BackgroundTasks = None,
    kernel: Kernel = Depends(get_kernel),
    download_queue: DownloadQueueService = Depends(get_download_queue),
    request_id: str = Depends(get_request_id),
) -> DownloadStartResponse:
    if not data.book_id:
        return error_response(
            "book_id required",
            status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.BOOK_ID_REQUIRED,
        )

    output_plugin = kernel["output"]
    if data.output_dir:
        success, message, output_dir = output_plugin.validate_dir(data.output_dir)
        if not success:
            return error_response(
                str(message),
                status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_OUTPUT_DIR,
            )
    else:
        output_dir = output_plugin.get_default_dir()

    try:
        formats = DownloaderPlugin.parse_formats(data.format)
    except ValueError as exc:
        return error_response(
            str(exc),
            status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INVALID_FORMAT,
        )

    selected_chapters = data.chapters
    if selected_chapters is not None:
        unsupported = sorted(
            fmt
            for fmt in formats
            if not DownloaderPlugin.supports_chapter_selection(fmt)
        )
        if unsupported:
            return error_response(
                (
                    f"Chapter selection not supported for: {', '.join(unsupported)}. "
                    "Remove 'chapters' or use chapter-compatible formats."
                ),
                status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.CHAPTERS_NOT_SUPPORTED_FOR_FORMAT,
                details={"unsupported_formats": unsupported},
            )

    queued_job: dict[str, Any] = download_queue.enqueue(
        book_id=data.book_id,
        output_dir=output_dir,
        formats=formats,
        selected_chapters=selected_chapters,
        skip_images=data.skip_images,
    )

    job_id = str(queued_job["job_id"])

    # Schedule background tasks if available
    if background_tasks:
        # Clean up old files periodically
        background_tasks.add_task(
            cleanup_old_files_task,
            output_dir,
            max_age_hours=24,
            file_extensions=(".pdf", ".epub"),
        )

        # Log progress notification
        background_tasks.add_task(
            notify_progress_task,
            job_id,
            download_queue,
            request_id,
        )

        logger.info(
            "[%s] Scheduled background tasks for job %s",
            request_id,
            job_id,
        )

    return DownloadStartResponse(
        status=str(queued_job.get("status", "queued")),
        book_id=data.book_id,
        job_id=job_id,
        queue_position=(
            int(queued_job["queue_position"])
            if queued_job.get("queue_position") is not None
            else None
        ),
    )
