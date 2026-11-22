"""Shared API response helpers."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from fastapi.responses import JSONResponse

from web.schemas import ErrorResponse

if TYPE_CHECKING:
    from collections.abc import Mapping


class ErrorCode(StrEnum):
    """Stable error codes exposed by the API."""

    BAD_REQUEST = "bad_request"
    INTERNAL_ERROR = "internal_error"
    INVALID_BOOK_ID = "invalid_book_id"
    INVALID_COOKIES_PAYLOAD = "invalid_cookies_payload"
    INVALID_SESSION_AFTER_COOKIES = "invalid_session_after_cookies"
    COOKIES_SAVE_FAILED = "cookies_save_failed"
    BOOK_CHAPTERS_FAILED = "book_chapters_failed"
    BOOK_FETCH_FAILED = "book_fetch_failed"
    BOOK_ID_REQUIRED = "book_id_required"
    INVALID_OUTPUT_DIR = "invalid_output_dir"
    INVALID_FORMAT = "invalid_format"
    CHAPTERS_NOT_SUPPORTED_FOR_FORMAT = "chapters_not_supported_for_format"
    PATH_REQUIRED = "path_required"
    PATH_NOT_FOUND = "path_not_found"
    PATH_OUTSIDE_OUTPUT_DIR = "path_outside_output_dir"
    REVEAL_FAILED = "reveal_failed"
    AUTH_REQUIRED = "auth_required"
    SEARCH_FAILED = "search_failed"
    JOB_NOT_FOUND = "job_not_found"
    CROSS_ORIGIN_BLOCKED = "cross_origin_blocked"
    RATE_LIMITED = "rate_limited"
    REQUEST_TOO_LARGE = "request_too_large"


def error_response(
    message: str,
    status_code: int,
    code: ErrorCode | str = ErrorCode.BAD_REQUEST,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the stable error payload: ``error``, ``code`` and optional ``details``."""
    if not (400 <= status_code < 600):
        raise ValueError(f"error_response needs a 4xx/5xx status, got {status_code}")
    payload = ErrorResponse(error=message, code=str(code), details=details).model_dump(
        exclude_none=True
    )
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


def sse_event(event: str, payload: dict[str, Any]) -> str:
    """Serialize one Server-Sent Event frame with a compact JSON payload."""
    if not event or "\n" in event or "\r" in event:
        raise ValueError(f"sse_event: event name must not contain line breaks: {event!r}")
    try:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"sse_event: payload for event {event!r} is not JSON-serializable: {exc}"
        ) from exc
    return f"event: {event}\ndata: {data}\n\n"


def sse_comment(text: str = "") -> str:
    """Serialize an SSE comment line, used as a keepalive."""
    safe = text.replace("\n", " ").replace("\r", " ")
    return f": {safe}\n\n"
