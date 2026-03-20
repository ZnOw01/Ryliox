"""FastAPI dependency providers."""

from __future__ import annotations

import logging
from collections.abc import Callable
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
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


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
    try:
        queue.start()
    except Exception:
        logger.exception("Failed to start DownloadQueueService.")
        raise
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
        return request.method.upper() in _SAFE_METHODS

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

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
    request_scheme = forwarded_proto or request.url.scheme.lower()
    request_host_raw = forwarded_host or (request.url.hostname or "")
    request_host = _normalize_host(request_host_raw.split(":", 1)[0])
    forwarded_port_raw = request.headers.get("x-forwarded-port", "").split(",", 1)[0].strip()
    try:
        forwarded_port = int(forwarded_port_raw) if forwarded_port_raw else None
    except ValueError:
        logger.warning("Blocked invalid X-Forwarded-Port header: %r", forwarded_port_raw)
        return False
    if forwarded_port is not None and not (1 <= forwarded_port <= 65535):
        logger.warning("Blocked out-of-range X-Forwarded-Port header: %r", forwarded_port_raw)
        return False
    request_port = forwarded_port or request.url.port or _default_port_for_scheme(request_scheme)
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
