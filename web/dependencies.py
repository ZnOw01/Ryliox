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
    """Initialize all application-scoped services during startup."""
    app.state.session_store = SessionStore()
    app.state.kernel = create_default_kernel()
    app.state.download_queue = _build_download_queue()
    logger.info("Application services initialized.")


async def shutdown_app_services(app: FastAPI) -> None:
    """Stop services in a safe order during shutdown."""
    download_queue: DownloadQueueService | None = getattr(
        app.state, "download_queue", None
    )
    if download_queue is not None:
        try:
            download_queue.stop()
            logger.info("DownloadQueueService stopped.")
        except Exception:
            logger.exception("Error while stopping DownloadQueueService.")

    kernel: Kernel | None = getattr(app.state, "kernel", None)
    if kernel is not None and getattr(kernel, "http", None) is not None:
        try:
            await kernel.http.close()
            logger.info("Kernel HTTP session closed.")
        except Exception:
            logger.exception("Error while closing kernel HTTP session.")


def get_kernel(request: Request) -> Kernel:
    """Return the app-scoped kernel."""
    return request.app.state.kernel  # type: ignore[no-any-return]


def get_session_store(request: Request) -> SessionStore:
    """Return the app-scoped SessionStore."""
    return request.app.state.session_store  # type: ignore[no-any-return]


def get_download_queue(request: Request) -> DownloadQueueService:
    """Return the app-scoped DownloadQueueService."""
    return request.app.state.download_queue  # type: ignore[no-any-return]


def _normalize_host(host: str) -> str:
    return host.lower()


def _first_forwarded_value(value: str | None) -> str:
    if not value:
        return ""
    return value.split(",", 1)[0].strip()


def _default_port_for_scheme(scheme: str) -> int | None:
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _is_same_origin(request: Request) -> bool:
    """Return True when the request appears same-origin."""
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return True

    try:
        parsed_origin = urlparse(origin)
    except ValueError:
        logger.warning("Blocked malformed Origin header: %r", origin)
        return False

    origin_scheme = parsed_origin.scheme.lower()
    origin_host = _normalize_host(parsed_origin.hostname or "")
    if not origin_scheme or not origin_host:
        return False

    try:
        origin_port = parsed_origin.port or _default_port_for_scheme(origin_scheme)
    except ValueError:
        logger.warning("Blocked Origin header with invalid port: %r", origin)
        return False

    request_host_header = _first_forwarded_value(
        request.headers.get("x-forwarded-host")
    ) or request.headers.get("host", "").strip()
    request_scheme = _first_forwarded_value(
        request.headers.get("x-forwarded-proto")
    ) or request.url.scheme.lower()
    request_scheme = request_scheme.lower()

    if not request_host_header or not request_scheme:
        return False

    try:
        parsed_request = urlparse(f"{request_scheme}://{request_host_header}")
        request_port = parsed_request.port
    except ValueError:
        logger.warning("Blocked malformed Host header: %r", request_host_header)
        return False

    if request_port is None:
        forwarded_port = _first_forwarded_value(request.headers.get("x-forwarded-port"))
        if forwarded_port.isdigit():
            request_port = int(forwarded_port)
        else:
            request_port = _default_port_for_scheme(request_scheme)

    request_host = _normalize_host(parsed_request.hostname or "")
    if not request_host or origin_port is None or request_port is None:
        return False

    return (
        origin_scheme == request_scheme
        and origin_host == request_host
        and origin_port == request_port
    )


def require_same_origin(operation: str) -> Callable[[Request], None]:
    """Return a FastAPI dependency that blocks cross-origin requests."""

    def _guard(request: Request) -> None:
        if not _is_same_origin(request):
            raise ForbiddenOriginError(operation)

    return _guard
