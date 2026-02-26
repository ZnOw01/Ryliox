"""Authentication and session routes."""

from __future__ import annotations

import logging
from typing import Union

from fastapi import APIRouter, Body, Depends, HTTPException, status

from core.kernel import Kernel
from core.session_store import SessionStore, normalize_cookies_payload
from web.api_utils import ErrorCode
from web.dependencies import get_kernel, get_session_store, require_same_origin
from web.schemas import CookiesResponse, SaveCookiesResponse, StatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["auth"])

_CookiesBody = Union[dict, list, str, None]


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
    payload = normalize_cookies_payload(data)
    if not payload:
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

    try:
        session_store.save_cookies(payload)
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
    status_result: dict = await auth.get_status()

    if (
        not status_result.get("valid")
        and status_result.get("reason") != "network_error"
    ):
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
