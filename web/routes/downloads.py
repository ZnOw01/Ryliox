"""Download queue and progress routes."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from core.download_queue import DownloadQueueService
from core.kernel import Kernel
from plugins.downloader import DownloaderPlugin
from web.api_utils import ErrorCode, sse_comment, sse_event
from web.dependencies import get_download_queue, get_kernel, require_same_origin
from web.schemas import (
    CancelRequest,
    CancelResponse,
    DownloadRequest,
    DownloadStartResponse,
    ProgressResponse,
)

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


@router.get("/progress", response_model=ProgressResponse)
def progress(
    job_id: str | None = Query(default=None),
    download_queue: DownloadQueueService = Depends(get_download_queue),
) -> dict[str, Any]:
    return _progress_payload(download_queue.get_progress(job_id=job_id))


@router.get("/progress/stream")
async def progress_stream(
    job_id: str | None = Query(default=None),
    download_queue: DownloadQueueService = Depends(get_download_queue),
) -> StreamingResponse:
    async def event_stream():
        last_signature: str | None = None
        last_heartbeat_at = time.monotonic()
        progress_version = download_queue.get_progress_version()
        try:
            while True:
                snapshot = download_queue.get_progress(job_id=job_id)
                payload = _progress_payload(snapshot)
                signature = json.dumps(payload, sort_keys=True, separators=(",", ":"))

                if signature != last_signature:
                    last_signature = signature
                    yield sse_event("progress", payload)

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
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
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
    kernel: Kernel = Depends(get_kernel),
    download_queue: DownloadQueueService = Depends(get_download_queue),
) -> DownloadStartResponse:
    if not data.book_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "book_id required", "code": ErrorCode.BOOK_ID_REQUIRED},
        )

    output_plugin = kernel["output"]
    if data.output_dir:
        success, message, output_dir = output_plugin.validate_dir(data.output_dir)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": message, "code": ErrorCode.INVALID_OUTPUT_DIR},
            )
    else:
        output_dir = output_plugin.get_default_dir()

    try:
        formats = DownloaderPlugin.parse_formats(data.format)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": ErrorCode.INVALID_FORMAT},
        ) from exc

    selected_chapters = data.chapters
    if selected_chapters is not None:
        unsupported = sorted(
            fmt
            for fmt in formats
            if not DownloaderPlugin.supports_chapter_selection(fmt)
        )
        if unsupported:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": (
                        f"Chapter selection not supported for: {', '.join(unsupported)}. "
                        "Remove 'chapters' or use chapter-compatible formats."
                    ),
                    "code": ErrorCode.CHAPTERS_NOT_SUPPORTED_FOR_FORMAT,
                    "unsupported_formats": unsupported,
                },
            )

    queued_job: dict[str, Any] = download_queue.enqueue(
        book_id=data.book_id,
        output_dir=output_dir,
        formats=formats,
        selected_chapters=selected_chapters,
        skip_images=data.skip_images,
    )

    return DownloadStartResponse(
        status=str(queued_job.get("status", "queued")),
        book_id=data.book_id,
        job_id=str(queued_job["job_id"]),
        queue_position=(
            int(queued_job["queue_position"])
            if queued_job.get("queue_position") is not None
            else None
        ),
    )
