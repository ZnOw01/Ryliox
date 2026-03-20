"""Authentication and session routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status

from core.kernel import Kernel
from core.session_store import (
    SessionStore,
    normalize_cookie_records_payload,
)
from web.api_utils import ErrorCode
from web.dependencies import get_kernel, get_session_store, require_same_origin
from web.schemas import CookiesResponse, SaveCookiesResponse, StatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["auth"])

_CookiesBody = dict | list | str | None


def _restore_previous_cookies(
    session_store: SessionStore, kernel: Kernel, previous_cookies: list[dict]
) -> None:
    try:
        session_store.save_cookies(previous_cookies)
        kernel.http.reload_cookies()
    except Exception:
        logger.exception("No se pudieron restaurar cookies previas.")


@router.get("/status", response_model=StatusResponse)
async def auth_status(
    kernel: Kernel = Depends(get_kernel),
    session_store: SessionStore = Depends(get_session_store),
) -> StatusResponse:
    """Retorna el estado de autenticación de la sesión actual."""
    auth = kernel["auth"]
    result: dict = await auth.get_status()
    return StatusResponse(
        valid=bool(result.get("valid")),
        reason=result.get("reason"),
        has_cookies=session_store.has_cookies(),
    )


@router.post(
    "/cookies",
    response_model=SaveCookiesResponse,
    dependencies=[Depends(require_same_origin("save_cookies"))],
)
async def save_cookies(
    data: _CookiesBody = Body(default=None),
    kernel: Kernel = Depends(get_kernel),
    session_store: SessionStore = Depends(get_session_store),
) -> SaveCookiesResponse:
    """Guarda cookies de sesión y verifica que autentiquen correctamente."""
    cookie_records = normalize_cookie_records_payload(data)
    if not cookie_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": (
                    "Invalid cookie data. Expected a cookie JSON object, "
                    "EditThisCookie JSON array/object, or 'name=value; ...' string."
                ),
                "code": ErrorCode.INVALID_COOKIES_PAYLOAD,
            },
        )

    previous_cookies = session_store.get_cookie_records()

    try:
        session_store.save_cookies(cookie_records)
    except Exception as exc:
        logger.exception("Error al guardar cookies en SessionStore.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(exc), "code": ErrorCode.COOKIES_SAVE_FAILED},
        ) from exc

    try:
        kernel.http.reload_cookies()
    except Exception as exc:
        logger.warning("reload_cookies falló tras guardar: %s", exc)

    auth = kernel["auth"]
    try:
        status_result: dict = await auth.get_status()
    except Exception as exc:
        logger.warning("Validacion de cookies fallo por error inesperado: %s", exc)
        _restore_previous_cookies(session_store, kernel, previous_cookies)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Unable to validate cookies right now. Please try again.",
                "code": ErrorCode.COOKIES_VALIDATION_UNAVAILABLE,
            },
        ) from exc

    if status_result.get("reason") == "network_error":
        _restore_previous_cookies(session_store, kernel, previous_cookies)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": (
                    "Unable to validate cookies because the upstream auth check "
                    "is temporarily unavailable. Previous session was restored."
                ),
                "code": ErrorCode.COOKIES_VALIDATION_UNAVAILABLE,
            },
        )

    if not status_result.get("valid"):
        _restore_previous_cookies(session_store, kernel, previous_cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": (
                    "Cookies saved but session is still invalid. "
                    "Use DevTools Network 'Cookie' header or EditThisCookie export "
                    "including HttpOnly cookies."
                ),
                "code": ErrorCode.INVALID_SESSION_AFTER_COOKIES,
            },
        )

    return SaveCookiesResponse(success=True)


@router.get(
    "/cookies",
    response_model=CookiesResponse,
    dependencies=[Depends(require_same_origin("get_cookies"))],
)
def get_cookies(
    session_store: SessionStore = Depends(get_session_store),
) -> CookiesResponse:
    """Retorna las cookies de sesión almacenadas actualmente."""
    return CookiesResponse(cookies=session_store.get_cookies())
