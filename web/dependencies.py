"""FastAPI dependency providers."""

from __future__ import annotations

import logging
from typing import Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request, status

import config
from core import create_default_kernel
from core.download_queue import DownloadQueueService
from core.kernel import Kernel
from core.session_store import SessionStore

logger = logging.getLogger(__name__)

DOWNLOAD_QUEUE_DB = config.DATA_DIR / "download_jobs.sqlite3"
DOWNLOAD_ERROR_LOG_DIR = config.DATA_DIR / "logs"
QUEUE_POLL_INTERVAL_SECONDS: float = 0.5


class ForbiddenOriginError(Exception):
    """Raised when a mutating endpoint receives a cross-origin request."""

    http_status = status.HTTP_403_FORBIDDEN

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Cross-origin request blocked for '{operation}'.")


def _build_download_queue() -> DownloadQueueService:
    queue = DownloadQueueService(
        kernel_factory=create_default_kernel,
        db_path=DOWNLOAD_QUEUE_DB,
        error_log_dir=DOWNLOAD_ERROR_LOG_DIR,
        poll_interval_seconds=QUEUE_POLL_INTERVAL_SECONDS,
    )
    queue.start()
    return queue


def initialize_app_services(app: FastAPI) -> None:
    """Inicializa todos los servicios con scope de app durante el startup.

    Se llama una sola vez desde el lifespan. Las dependencias ``get_*``
    asumen que este método ya se ejecutó y simplemente leen del estado.
    """
    app.state.session_store = SessionStore()
    app.state.kernel = create_default_kernel()
    app.state.download_queue = _build_download_queue()
    logger.info("Servicios de app inicializados correctamente.")


async def shutdown_app_services(app: FastAPI) -> None:
    """Para los servicios de app de forma ordenada durante el shutdown."""
    download_queue: DownloadQueueService | None = getattr(
        app.state, "download_queue", None
    )
    if download_queue is not None:
        try:
            download_queue.stop()
            logger.info("DownloadQueueService detenido.")
        except Exception:
            logger.exception("Error al detener DownloadQueueService.")

    kernel: Kernel | None = getattr(app.state, "kernel", None)
    if kernel is not None and getattr(kernel, "http", None) is not None:
        try:
            await kernel.http.close()
            logger.info("Sesión HTTP del kernel cerrada.")
        except Exception:
            logger.exception("Error al cerrar la sesión HTTP del kernel.")


def get_kernel(request: Request) -> Kernel:
    """Retorna el kernel con scope de app."""
    return request.app.state.kernel  # type: ignore[no-any-return]


def get_session_store(request: Request) -> SessionStore:
    """Retorna el SessionStore con scope de app."""
    return request.app.state.session_store  # type: ignore[no-any-return]


def get_download_queue(request: Request) -> DownloadQueueService:
    """Retorna el DownloadQueueService con scope de app."""
    return request.app.state.download_queue  # type: ignore[no-any-return]


def _normalize_host(host: str) -> str:
    """Normaliza un host a minúsculas."""
    return host.lower()


def _default_port_for_scheme(scheme: str) -> int | None:
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _is_same_origin(request: Request) -> bool:
    """Retorna True si el request es same-origin o no tiene header Origin."""
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return True

    try:
        parsed_origin = urlparse(origin)
    except ValueError:
        logger.warning("Header Origin malformado bloqueado: %r", origin)
        return False

    origin_scheme = parsed_origin.scheme.lower()
    origin_host = _normalize_host(parsed_origin.hostname or "")
    if not origin_scheme or not origin_host:
        return False

    try:
        origin_port = parsed_origin.port or _default_port_for_scheme(origin_scheme)
    except ValueError:
        logger.warning("Header Origin con puerto inválido bloqueado: %r", origin)
        return False

    request_host_header = request.headers.get("host", "").strip()
    request_scheme = request.url.scheme.lower()
    if not request_host_header or not request_scheme:
        return False

    try:
        parsed_request = urlparse(f"{request_scheme}://{request_host_header}")
        request_port = parsed_request.port or _default_port_for_scheme(request_scheme)
    except ValueError:
        logger.warning("Header Host malformado bloqueado: %r", request_host_header)
        return False

    request_host = _normalize_host(parsed_request.hostname or "")
    if not request_host or origin_port is None or request_port is None:
        return False

    return (
        origin_scheme == request_scheme
        and origin_host == request_host
        and origin_port == request_port
    )


def require_same_origin(operation: str) -> Callable[[Request], None]:
    """Retorna una dependencia FastAPI que bloquea requests cross-origin.

    Uso::

        @router.post("/sensitive")
        def endpoint(_: None = Depends(require_same_origin("sensitive_op"))):
            ...
    """

    def _guard(request: Request) -> None:
        if not _is_same_origin(request):
            raise ForbiddenOriginError(operation)

    return _guard
