"""FastAPI dependency providers with Dependency Inversion and OWASP security.

Implements:
- OWASP A01: Access Control (same-origin validation)
- OWASP A03/A10: Input validation delegated to :mod:`core.validators`
"""

from __future__ import annotations

import ipaddress
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from fastapi import FastAPI, Request, status

import config
from core import create_default_kernel

# New architectural imports (Dependency Inversion)
from core.repository import DownloadJobRepository
from core.services import DownloadQueueService
from core.session_store import SessionStore

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from core.interfaces import IDownloadJobRepository
    from core.kernel import Kernel

logger = logging.getLogger(__name__)

# Queue storage and timing come straight from configuration so that
# ``RYLIOX_QUEUE__*`` environment overrides apply. The module-level names are
# kept as aliases for backward-compatible imports.
DOWNLOAD_QUEUE_DB = config.DOWNLOAD_QUEUE_DB
DOWNLOAD_ERROR_LOG_DIR = config.DOWNLOAD_ERROR_LOG_DIR
QUEUE_POLL_INTERVAL_SECONDS: float = config.SETTINGS.queue.poll_interval_seconds
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class ForbiddenOriginError(Exception):
    """Raised when a mutating endpoint receives a cross-origin request."""

    http_status = status.HTTP_403_FORBIDDEN

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Cross-origin request blocked for '{operation}'.")


def _build_download_queue(
    # Dependency injection: se puede pasar repository custom para testing
    repository: IDownloadJobRepository | None = None,
) -> DownloadQueueService:
    """Build DownloadQueueService with dependency injection."""

    async def _async_kernel_factory() -> Kernel:
        return create_default_kernel()

    # Si no se provee repository, crear el default
    if repository is None:
        repository = DownloadJobRepository(
            db_path=config.DOWNLOAD_QUEUE_DB,
            terminal_job_retention=config.SETTINGS.queue.terminal_job_retention,
        )

    # Inyección de dependencias al service layer
    queue = DownloadQueueService(
        kernel_factory=_async_kernel_factory,
        repository=repository,  # Inyección del repository
        error_log_dir=config.DOWNLOAD_ERROR_LOG_DIR,
        poll_interval_seconds=QUEUE_POLL_INTERVAL_SECONDS,
        max_queued_jobs=config.SETTINGS.queue.max_queued_jobs,
        download_timeout_seconds=config.SETTINGS.http.request_timeout_seconds,
    )
    queue.start()
    return queue


async def initialize_app_services(
    app: FastAPI,
    # Permite inyección de dependencias para testing
    repository: IDownloadJobRepository | None = None,
) -> None:
    """Initialize all application-scoped services during startup."""
    from core.cache import clear_all_caches, start_all_cleanup_tasks

    await clear_all_caches()
    await start_all_cleanup_tasks()
    app.state.session_store = SessionStore()
    # Initialize kernel and enter its async context so plugins can use
    # ``self.kernel.http`` for the lifetime of the app.
    kernel = create_default_kernel()
    await kernel.__aenter__()
    app.state.kernel = kernel
    # Usar la factory con inyección de dependencias
    app.state.download_queue = _build_download_queue(repository=repository)
    logger.info("Application services initialized with architectural improvements.")


async def shutdown_app_services(app: FastAPI) -> None:
    """Stop services in a safe order during shutdown."""
    from core.cache import stop_all_cleanup_tasks

    await stop_all_cleanup_tasks()
    download_queue: DownloadQueueService | None = getattr(app.state, "download_queue", None)
    if download_queue is not None:
        try:
            download_queue.stop(config.SETTINGS.queue.shutdown_timeout_seconds)
            logger.info("DownloadQueueService stopped.")
        except Exception:
            logger.exception("Error while stopping DownloadQueueService.")

    kernel: Kernel | None = getattr(app.state, "kernel", None)
    if kernel is not None:
        try:
            await kernel.__aexit__(None, None, None)
            logger.info("Kernel HTTP session closed.")
        except Exception:
            logger.exception("Error while closing kernel HTTP session.")


# === Dependency Injection Providers ===


def get_kernel(request: Request) -> Generator[Kernel, None, None]:
    """Yield the app-scoped kernel."""
    yield request.app.state.kernel


def get_session_store(request: Request) -> Generator[SessionStore, None, None]:
    """Yield the app-scoped SessionStore."""
    yield request.app.state.session_store


def get_download_queue(request: Request) -> Generator[DownloadQueueService, None, None]:
    """Yield the app-scoped DownloadQueueService."""
    yield request.app.state.download_queue


def get_request_id(request: Request) -> str:
    """Return the request ID from request state for tracing."""
    return getattr(request.state, "request_id", "unknown")


def _normalize_host(host: str) -> str:
    return host.lower()


def _first_forwarded_value(value: str | None) -> str:
    if not value:
        return ""
    return value.split(",", 1)[0].strip()


def _is_loopback_host(host: str) -> bool:
    if not host or host.lower() in ("127.0.0.1", "localhost", "::1", "testclient"):
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


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

    client_host = request.client.host if request.client else ""
    is_trusted_peer = (
        _is_loopback_host(client_host) or config.SETTINGS.security.allow_unauthenticated_local_proxy
    )

    if is_trusted_peer and request.headers.get("x-forwarded-host"):
        request_host_header = _first_forwarded_value(request.headers.get("x-forwarded-host"))
    else:
        request_host_header = request.headers.get("host", "").strip()

    if is_trusted_peer and request.headers.get("x-forwarded-proto"):
        request_scheme = (
            _first_forwarded_value(request.headers.get("x-forwarded-proto"))
            or request.url.scheme.lower()
        )
    else:
        request_scheme = request.url.scheme.lower()
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
        forwarded_port = (
            _first_forwarded_value(request.headers.get("x-forwarded-port"))
            if is_trusted_peer
            else ""
        )
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
    """Return a FastAPI dependency that blocks cross-origin requests.

    Safe HTTP methods (GET, HEAD, OPTIONS, TRACE) are allowed without an
    ``Origin`` header, matching the spirit of OWASP's "Origin header is
    only required for unsafe methods" guidance.

    For state-changing methods (POST/PUT/PATCH/DELETE) an ``Origin`` header
    that matches the request's host is always required, regardless of the
    current environment.
    """

    def _guard(request: Request) -> None:
        if not _is_same_origin(request):
            raise ForbiddenOriginError(operation)

    return _guard
