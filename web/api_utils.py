"""Shared API response helpers."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from web.schemas import ErrorResponse


class ErrorCode(StrEnum):
    """Stable error codes exposed by the API."""

    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNPROCESSABLE = "unprocessable"
    INTERNAL_ERROR = "internal_error"
    FORBIDDEN_ORIGIN = "forbidden_origin"
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
    REVEAL_FAILED = "reveal_failed"


def error_response(
    message: str,
    status_code: int,
    code: ErrorCode | str = ErrorCode.BAD_REQUEST,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Construye un payload de error estable con ``code`` y ``details`` opcionales.

    Args:
        message:     Descripción legible del error.
        status_code: Código HTTP. Debe ser 4xx o 5xx.
        code:        Código de error de máquina (``ErrorCode``).
        details:     Campos adicionales opcionales para debugging.
    """
    if not (400 <= status_code < 600):
        raise ValueError(
            f"error_response requiere un status 4xx/5xx, recibido: {status_code}"
        )
    payload = ErrorResponse(error=message, code=str(code), details=details).model_dump(
        exclude_none=True
    )
    return JSONResponse(content=payload, status_code=status_code)


def not_found_response(
    message: str, code: ErrorCode | str = ErrorCode.NOT_FOUND
) -> JSONResponse:
    """Atajo para 404."""
    return error_response(message, status.HTTP_404_NOT_FOUND, code=code)


def bad_request_response(
    message: str, code: ErrorCode | str = ErrorCode.BAD_REQUEST
) -> JSONResponse:
    """Atajo para 400."""
    return error_response(message, status.HTTP_400_BAD_REQUEST, code=code)


def internal_error_response(message: str = "Internal server error.") -> JSONResponse:
    """Atajo para 500."""
    return error_response(
        message, status.HTTP_500_INTERNAL_SERVER_ERROR, code=ErrorCode.INTERNAL_ERROR
    )


def sse_event(event: str, payload: dict[str, Any]) -> str:
    """Serializa un frame Server-Sent Event con payload JSON compacto.

    Args:
        event:   Nombre del evento. No puede contener ``\\n`` ni ``\\r``.
        payload: Datos serializables a JSON.

    Raises:
        ValueError:  Si ``event`` contiene caracteres de nueva línea.
        TypeError:   Si ``payload`` contiene valores no serializables.
    """
    if not event or "\n" in event or "\r" in event:
        raise ValueError(
            f"sse_event: el nombre de evento no puede contener saltos de línea: {event!r}"
        )
    try:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"sse_event: payload para evento {event!r} no es JSON-serializable: {exc}"
        ) from exc
    return f"event: {event}\ndata: {data}\n\n"


def sse_comment(text: str = "") -> str:
    """Emite un comentario SSE, útil como keepalive/heartbeat.

    Example::

        yield sse_comment("keepalive")  # →  ': keepalive\\n\\n'
    """
    safe = text.replace("\n", " ").replace("\r", " ")
    return f": {safe}\n\n"
