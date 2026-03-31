"""FastAPI dependency providers with Dependency Inversion and OWASP security.

Implements:
- OWASP A01: Access Control (same-origin validation)
- OWASP A03: Input validation
- OWASP A10: SSRF protection
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Callable, Generator, Awaitable
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, status

import config
from core import create_default_kernel
from core.kernel import Kernel
from core.session_store import SessionStore
from core.validators import (
    validate_book_id,
    validate_url,
    validate_file_path,
    validate_user_input,
    ValidationError,
)
from core.audit import audit_security, AuditEventType

# New architectural imports (Dependency Inversion)
from core.interfaces import (
    IDownloadJobRepository,
    IDownloadQueueService,
)
from core.repository import DownloadJobRepository
from core.services import DownloadQueueService as ModernDownloadQueueService

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


def _build_download_queue(
    # Dependency injection: se puede pasar repository custom para testing
    repository: IDownloadJobRepository | None = None,
) -> DownloadQueueService:
    """Build DownloadQueueService with dependency injection."""

    async def _async_kernel_factory() -> Kernel:
        return await create_default_kernel()

    # Si no se provee repository, crear el default
    if repository is None:
        repository = DownloadJobRepository(
            db_path=DOWNLOAD_QUEUE_DB,
            terminal_job_retention=500,
        )

    # Inyección de dependencias al service layer
    queue = ModernDownloadQueueService(
        kernel_factory=_async_kernel_factory,
        repository=repository,  # Inyección del repository
        error_log_dir=DOWNLOAD_ERROR_LOG_DIR,
        poll_interval_seconds=QUEUE_POLL_INTERVAL_SECONDS,
    )
    queue.start()
    return queue


async def initialize_app_services(
    app: FastAPI,
    # Permite inyección de dependencias para testing
    repository: IDownloadJobRepository | None = None,
) -> None:
    """Initialize all application-scoped services during startup."""
    app.state.session_store = SessionStore()
    # Initialize kernel with async context manager
    kernel = await create_default_kernel()
    app.state.kernel = kernel
    # Usar la factory con inyección de dependencias
    app.state.download_queue = _build_download_queue(repository=repository)
    logger.info("Application services initialized with architectural improvements.")


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


# === Dependency Injection Providers ===


class DependencyProvider:
    """
    Provider centralizado para inyección de dependencias.
    Facilita testing con mocks y cambio de implementaciones.
    """

    _repository: IDownloadJobRepository | None = None
    _queue_service: IDownloadQueueService | None = None

    @classmethod
    def configure(
        cls,
        repository: IDownloadJobRepository | None = None,
        queue_service: IDownloadQueueService | None = None,
    ) -> None:
        """Configura las dependencias (útil para testing)."""
        cls._repository = repository
        cls._queue_service = queue_service

    @classmethod
    def reset(cls) -> None:
        """Resetea a defaults (útil entre tests)."""
        cls._repository = None
        cls._queue_service = None

    @classmethod
    def get_repository(cls) -> IDownloadJobRepository:
        """Factory para el repository."""
        if cls._repository is None:
            cls._repository = DownloadJobRepository(
                db_path=DOWNLOAD_QUEUE_DB,
                terminal_job_retention=500,
            )
        return cls._repository

    @classmethod
    def get_queue_service(
        cls, kernel_factory: Callable[[], Awaitable[Kernel]]
    ) -> IDownloadQueueService:
        """Factory para el queue service."""
        if cls._queue_service is None:
            cls._queue_service = ModernDownloadQueueService(
                kernel_factory=kernel_factory,
                repository=cls.get_repository(),
                error_log_dir=DOWNLOAD_ERROR_LOG_DIR,
                poll_interval_seconds=QUEUE_POLL_INTERVAL_SECONDS,
            )
        return cls._queue_service


def get_kernel(request: Request) -> Generator[Kernel, None, None]:
    """Yield the app-scoped kernel with proper exception handling."""
    kernel = request.app.state.kernel
    try:
        yield kernel
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in kernel dependency: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error in kernel service",
        ) from exc


def get_session_store(request: Request) -> Generator[SessionStore, None, None]:
    """Yield the app-scoped SessionStore with proper exception handling."""
    session_store = request.app.state.session_store
    try:
        yield session_store
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in session store dependency: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error in session service",
        ) from exc


def get_download_queue(request: Request) -> Generator[DownloadQueueService, None, None]:
    """Yield the app-scoped DownloadQueueService with proper exception handling."""
    download_queue = request.app.state.download_queue
    try:
        yield download_queue
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in download queue dependency: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error in download queue service",
        ) from exc


def get_repository() -> IDownloadJobRepository:
    """
    Dependency provider para IDownloadJobRepository.
    Permite inyección del repository en endpoints.
    """
    return DependencyProvider.get_repository()


def get_request_id(request: Request) -> str:
    """Return the request ID from request state for tracing."""
    return getattr(request.state, "request_id", "unknown")


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

    request_host_header = (
        _first_forwarded_value(request.headers.get("x-forwarded-host"))
        or request.headers.get("host", "").strip()
    )
    request_scheme = (
        _first_forwarded_value(request.headers.get("x-forwarded-proto"))
        or request.url.scheme.lower()
    )
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


# === OWASP Input Validation Functions ===


def validate_book_id_dependency(book_id: str) -> str:
    """Validate book_id parameter for injection prevention (OWASP A03).

    Args:
        book_id: The book ID to validate

    Returns:
        Validated book ID

    Raises:
        HTTPException: If validation fails
    """
    try:
        return validate_book_id(book_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": str(exc),
                "code": "invalid_book_id",
                "field": exc.field,
            },
        ) from exc


def validate_url_dependency(url: str, allowed_hosts: set[str] | None = None) -> str:
    """Validate URL for SSRF prevention (OWASP A10).

    Args:
        url: The URL to validate
        allowed_hosts: Optional whitelist of allowed hostnames

    Returns:
        Validated URL

    Raises:
        HTTPException: If validation fails
    """
    try:
        return validate_url(url, allowed_hosts)
    except ValidationError as exc:
        # Log security event for SSRF attempt
        logger.warning(
            "SSRF prevention: URL validation failed for %s: %s", url[:50], exc.reason
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid or unsafe URL",
                "code": "invalid_url",
            },
        ) from exc


def validate_path_dependency(
    path: str, base_dir: str | None = None, must_exist: bool = False
) -> str:
    """Validate file path for path traversal prevention (OWASP A03).

    Args:
        path: The file path to validate
        base_dir: Base directory that path must be under
        must_exist: Whether file must exist

    Returns:
        Validated path string

    Raises:
        HTTPException: If validation fails
    """
    try:
        from pathlib import Path

        base = Path(base_dir) if base_dir else None
        validated = validate_file_path(path, base, must_exist)
        return str(validated)
    except ValidationError as exc:
        # Log security event for path traversal attempt
        logger.warning(
            "Path traversal prevention: validation failed for %s: %s",
            path[:50],
            exc.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid file path",
                "code": "invalid_path",
            },
        ) from exc


def validate_input_dependency(
    text: str, allow_html: bool = False, max_length: int = 10000
) -> str:
    """Validate user input for XSS prevention (OWASP A03).

    Args:
        text: The user input to validate
        allow_html: Whether to allow safe HTML
        max_length: Maximum allowed length

    Returns:
        Validated and sanitized text

    Raises:
        HTTPException: If validation fails
    """
    try:
        return validate_user_input(text, allow_html, max_length)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": str(exc),
                "code": "invalid_input",
                "field": exc.field,
            },
        ) from exc


class SSRFProtection:
    """SSRF protection for outbound HTTP requests (OWASP A10)."""

    # Blocked IP ranges (private, loopback, link-local)
    _BLOCKED_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),  # Loopback
        ipaddress.ip_network("10.0.0.0/8"),  # Private
        ipaddress.ip_network("172.16.0.0/12"),  # Private
        ipaddress.ip_network("192.168.0.0/16"),  # Private
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),  # IPv6 private
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    # Blocked hostnames
    _BLOCKED_HOSTS = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
    }

    @classmethod
    def is_safe_url(cls, url: str) -> tuple[bool, str]:
        """Check if a URL is safe from SSRF attacks.

        Returns:
            Tuple of (is_safe, reason)
        """
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            return False, f"Invalid URL format: {exc}"

        hostname = parsed.hostname
        if not hostname:
            return False, "URL missing hostname"

        # Check blocked hostnames
        if hostname.lower() in cls._BLOCKED_HOSTS:
            return False, f"Hostname '{hostname}' is blocked"

        # Check if hostname is an IP in blocked ranges
        try:
            ip = ipaddress.ip_address(hostname)
            for network in cls._BLOCKED_NETWORKS:
                if ip in network:
                    return False, f"IP {hostname} is in blocked range {network}"
        except ValueError:
            # Not an IP, continue
            pass

        # Check scheme
        if parsed.scheme not in ("http", "https"):
            return False, f"Scheme '{parsed.scheme}' not allowed"

        return True, ""

    @classmethod
    def assert_safe_url(cls, url: str) -> None:
        """Assert URL is safe, raise HTTPException if not."""
        is_safe, reason = cls.is_safe_url(url)
        if not is_safe:
            logger.warning("SSRF protection blocked URL: %s - %s", url[:50], reason)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "URL not allowed for security reasons",
                    "code": "ssrf_blocked",
                },
            )


# CSRF Protection utilities
class CSRFProtection:
    """CSRF token generation and validation (OWASP A08)."""

    def __init__(self, token_length: int = 32, ttl: int = 3600):
        self._token_length = token_length
        self._ttl = ttl
        self._tokens: dict[
            str, tuple[str, float]
        ] = {}  # session_id -> (token, expires)
        self._lock = asyncio.Lock()

    async def generate_token(self, session_id: str) -> str:
        """Generate a new CSRF token for a session."""
        import secrets
        import time

        token = secrets.token_urlsafe(self._token_length)
        expires = time.time() + self._ttl

        async with self._lock:
            self._tokens[session_id] = (token, expires)

        return token

    async def validate_token(self, session_id: str, provided_token: str) -> bool:
        """Validate a CSRF token."""
        import time

        async with self._lock:
            if session_id not in self._tokens:
                return False

            stored_token, expires = self._tokens[session_id]

            # Check expiration
            if time.time() > expires:
                del self._tokens[session_id]
                return False

            # Constant-time comparison
            import hmac

            is_valid = hmac.compare_digest(stored_token, provided_token)

            # Rotate token after use (one-time use pattern)
            if is_valid:
                del self._tokens[session_id]

            return is_valid

    async def cleanup_expired(self) -> int:
        """Clean up expired tokens. Returns count removed."""
        import time

        async with self._lock:
            now = time.time()
            expired = [
                sid for sid, (_, expires) in self._tokens.items() if now > expires
            ]
            for sid in expired:
                del self._tokens[sid]
            return len(expired)


# Global CSRF protection instance
_csrf_protection: CSRFProtection | None = None


def get_csrf_protection() -> CSRFProtection:
    """Get or create global CSRF protection instance."""
    global _csrf_protection
    if _csrf_protection is None:
        token_length = getattr(config.SETTINGS, "csrf_token_length", 32)
        ttl = getattr(config.SETTINGS, "csrf_token_ttl", 3600)
        _csrf_protection = CSRFProtection(token_length, ttl)
    return _csrf_protection


def require_same_origin(operation: str) -> Callable[[Request], None]:
    """Return a FastAPI dependency that blocks cross-origin requests."""

    def _guard(request: Request) -> None:
        if not _is_same_origin(request):
            raise ForbiddenOriginError(operation)

    return _guard
