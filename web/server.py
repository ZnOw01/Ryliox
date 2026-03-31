"""FastAPI web server with observability features and OWASP security."""

from __future__ import annotations

import logging
import os
import secrets
import sys
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Final

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging_config import (
    configure_logging,
    log_context,
    set_request_id,
    set_book_id,
    set_job_id,
)
from core.metrics import metrics
from core.audit import audit_security, audit_log, AuditEventType, AuditSeverity
from web.api_utils import error_response
from web.dependencies import (
    ForbiddenOriginError,
    initialize_app_services,
    shutdown_app_services,
)

logger = logging.getLogger(__name__)

APP_VERSION: Final[str] = os.getenv("APP_VERSION", "dev")
FRONTEND_DIST: Final[Path] = (
    Path(__file__).resolve().parent.parent / "frontend" / "dist"
)

_CORS_ORIGINS_RAW: Final[str] = os.getenv(
    "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
).strip()
_CORS_ORIGINS: Final[list[str]] = (
    ["*"]
    if _CORS_ORIGINS_RAW == "*"
    else [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]
)

_CORS_METHODS: Final[list[str]] = ["GET", "POST", "DELETE"]
_CORS_HEADERS: Final[list[str]] = ["Content-Type", "Authorization", "X-Request-ID"]

_RATE_LIMIT_MAX_REQUESTS: Final[int] = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5"))
_RATE_LIMIT_WINDOW_SECONDS: Final[int] = int(
    os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
)

_IS_PRODUCTION: Final[bool] = os.getenv("ENVIRONMENT", "development").lower() in (
    "production",
    "prod",
)

_NO_CACHE_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

# API response caching configuration
_CACHEABLE_API_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "/api/status",
        "/api/book/",
        "/api/chapters/",
        "/api/search",
    }
)
_API_CACHE_MAX_AGE: Final[int] = int(
    os.getenv("API_CACHE_MAX_AGE", "60")
)  # 1 minute default
_STATIC_CACHE_MAX_AGE: Final[int] = int(
    os.getenv("STATIC_CACHE_MAX_AGE", "3600")
)  # 1 hour for static files

_SW_UNREGISTER_SCRIPT: Final[str] = """\
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of clients) client.navigate(client.url);
  })().catch(() => {}));
});
"""


class _RateLimiter:
    """Simple in-memory rate limiter per client IP and endpoint path."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[tuple[str, str], list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str, endpoint: str) -> bool:
        key = (client_ip, endpoint)
        now = time.monotonic()
        timestamps = self._requests[key]
        # Remove timestamps outside the window
        cutoff = now - self.window_seconds
        self._requests[key] = [ts for ts in timestamps if ts > cutoff]
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    def clear_old_entries(self) -> None:
        """Clear entries older than window to prevent memory growth."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        for key in list(self._requests.keys()):
            self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]
            if not self._requests[key]:
                del self._requests[key]


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


_RATE_LIMITED_ENDPOINTS: Final[frozenset[str]] = frozenset(
    {"/api/download", "/api/cookies"}
)
_rate_limiter: _RateLimiter | None = None


def _no_cache_response(content: str, media_type: str) -> Response:
    """Devuelve una respuesta con cabeceras que deshabilitan el caché."""
    return Response(content=content, media_type=media_type, headers=_NO_CACHE_HEADERS)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to assign a unique request ID for tracing and correlation."""

    async def dispatch(self, request: Request, call_next):
        # Try to get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4().hex[:16])

        # Store in request state and set in logging context
        request.state.request_id = request_id
        set_request_id(request_id)

        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Inicializa y apaga ordenadamente todos los servicios de la app."""
    import asyncio

    app.state.started_at = time.monotonic()
    app.state.app_version = APP_VERSION
    await initialize_app_services(app)

    # Configure structured logging
    configure_logging()

    with log_context():
        logger.info("App v%s iniciada with observability enabled.", APP_VERSION)

    # Periodic cleanup and metrics task
    cleanup_task: asyncio.Task | None = None

    async def _periodic_maintenance():
        while True:
            await asyncio.sleep(300)  # 5 minutes
            if _rate_limiter:
                _rate_limiter.clear_old_entries()

            # Update disk metrics
            from config import OUTPUT_DIR, DATA_DIR

            metrics.update_disk_usage(str(OUTPUT_DIR))
            metrics.update_disk_usage(str(DATA_DIR))

    cleanup_task = asyncio.create_task(_periodic_maintenance())

    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        await shutdown_app_services(app)
        with log_context():
            logger.info("App apagada correctamente.")


def create_app() -> FastAPI:
    """Construye la aplicación FastAPI con rutas API y hosting de estáticos."""
    from web.routes.auth import router as auth_router
    from web.routes.books import router as books_router
    from web.routes.downloads import router as downloads_router
    from web.routes.system import router as system_router
    from web.routes.metrics import router as metrics_router

    global _rate_limiter
    _rate_limiter = _RateLimiter(_RATE_LIMIT_MAX_REQUESTS, _RATE_LIMIT_WINDOW_SECONDS)

    # Conditionally enable API docs based on environment
    docs_url = "/docs" if not _IS_PRODUCTION else None
    redoc_url = "/redoc" if not _IS_PRODUCTION else None
    openapi_url = "/api/openapi.json" if not _IS_PRODUCTION else None

    app = FastAPI(
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=_lifespan,
    )

    @app.middleware("http")
    async def _logging_and_metrics_middleware(request: Request, call_next) -> Response:
        """Log all requests with timing information, request ID, and metrics."""
        start = time.time()

        # Set request ID in logging context
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            set_request_id(request_id)

        response = await call_next(request)
        duration = time.time() - start

        # Record HTTP metrics
        metrics.record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration,
        )

        # Log with context
        logger.info(
            "%s %s - %d - %.3fs",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration * 1000,
            },
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=_CORS_METHODS,
        allow_headers=_CORS_HEADERS,
        expose_headers=["Content-Disposition", "X-Request-ID"],
        max_age=600,
    )

    # Add request ID middleware first to capture request ID early
    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(ForbiddenOriginError)
    async def _handle_forbidden_origin(
        _: Request, exc: ForbiddenOriginError
    ) -> Response:
        metrics.record_error("forbidden_origin", "security")
        return error_response(str(exc), exc.http_status, code="forbidden_origin")

    @app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next) -> Response:
        """Apply rate limiting to specific mutating endpoints."""
        if _rate_limiter and request.url.path in _RATE_LIMITED_ENDPOINTS:
            client_ip = _get_client_ip(request)
            if not _rate_limiter.is_allowed(client_ip, request.url.path):
                request_id = getattr(request.state, "request_id", "unknown")
                logger.warning(
                    "Rate limit exceeded for IP=%s path=%s",
                    client_ip,
                    request.url.path,
                    extra={
                        "request_id": request_id,
                        "client_ip": client_ip,
                        "endpoint": request.url.path,
                        "event": "rate_limit_exceeded",
                    },
                )
                metrics.record_rate_limit_hit(request.url.path)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded. Please try again later.",
                        "code": "rate_limit_exceeded",
                    },
                )
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> Response:
        request_id = getattr(request.state, "request_id", "unknown")
        status_code = int(exc.status_code)
        if not 400 <= status_code < 600:
            status_code = 500

        # Record error metrics for 5xx errors
        if status_code >= 500:
            metrics.record_error("http_exception", "api")
            logger.error(
                "HTTP exception: status=%d, detail=%s, request_id=%s",
                status_code,
                str(exc.detail),
                request_id,
                extra={
                    "request_id": request_id,
                    "status_code": status_code,
                    "error_detail": str(exc.detail),
                },
            )

        detail = exc.detail
        if isinstance(detail, dict):
            message = str(
                detail.get("error") or detail.get("detail") or "Request failed"
            )
            code = str(detail.get("code") or "http_error")
            details: dict[str, Any] | None = None
            if isinstance(detail.get("details"), dict):
                details = dict(detail["details"])
            extra = {
                key: value
                for key, value in detail.items()
                if key not in {"error", "code", "details", "detail"}
            }
            if extra:
                details = {**(details or {}), **extra}
            return error_response(message, status_code, code=code, details=details)

        if isinstance(detail, str):
            return error_response(detail, status_code, code="http_error")

        return error_response(
            "Request failed",
            status_code,
            code="http_error",
            details={"detail": detail} if detail is not None else None,
        )

    @app.middleware("http")
    async def _disable_html_cache(request: Request, call_next):
        """Deshabilita el caché para archivos HTML."""
        response = await call_next(request)
        path = request.url.path
        content_type = response.headers.get("content-type", "").lower()

        if (
            path in {"/", "/index.html"}
            or path.endswith(".html")
            or "text/html" in content_type
        ):
            response.headers.update(_NO_CACHE_HEADERS)

        return response

    @app.middleware("http")
    async def _cache_api_responses(request: Request, call_next) -> Response:
        """Add cache headers to appropriate API responses."""
        response = await call_next(request)
        path = request.url.path

        # Only cache GET requests
        if request.method != "GET":
            return response

        # Skip if error response
        if response.status_code >= 400:
            return response

        # Add caching headers for cacheable API endpoints
        for prefix in _CACHEABLE_API_PREFIXES:
            if path.startswith(prefix):
                response.headers["Cache-Control"] = (
                    f"public, max-age={_API_CACHE_MAX_AGE}"
                )
                response.headers["Vary"] = "Accept-Encoding"
                break

        return response

    @app.middleware("http")
    async def _add_security_headers(request: Request, call_next) -> Response:
        """Add OWASP-compliant security headers to all responses."""
        response = await call_next(request)

        # OWASP A05: Security Misconfiguration - Secure headers
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS Protection (legacy but still useful as defense-in-depth)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy - limit referrer leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # OWASP A02: Cryptographic Failures - HSTS (only in production with TLS)
        if _IS_PRODUCTION and os.getenv("ENABLE_HSTS", "false").lower() == "true":
            hsts_max_age = int(os.getenv("HSTS_MAX_AGE", "31536000"))
            response.headers["Strict-Transport-Security"] = (
                f"max-age={hsts_max_age}; includeSubDomains; preload"
            )

        # Content Security Policy - strict but functional policy
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "media-src 'self'; "
            "object-src 'none'; "
            "child-src 'self'; "
            "worker-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests; "
            "block-all-mixed-content"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        # Permissions Policy - restrict browser features
        permissions_policy = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=(), "
            "xr-spatial-tracking=()"
        )
        response.headers["Permissions-Policy"] = permissions_policy

        # Cross-Origin policies - relaxed for external resource loading
        # COEP removed to allow displaying external images/content without CORP headers
        # This is necessary for a web scraper that displays content from various sources
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # Feature Policy (legacy name for Permissions-Policy)
        response.headers["Feature-Policy"] = permissions_policy

        return response

    # Trusted Host validation for production (OWASP A05)
    if _IS_PRODUCTION:
        allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[h.strip() for h in allowed_hosts if h.strip()],
        )

    # Input validation middleware (OWASP A03)
    @app.middleware("http")
    async def _validate_request_size(request: Request, call_next) -> Response:
        """Validate request size to prevent DoS."""
        content_length = request.headers.get("content-length")
        max_size = int(os.getenv("MAX_REQUEST_SIZE_MB", "10")) * 1024 * 1024

        if content_length and int(content_length) > max_size:
            request_id = getattr(request.state, "request_id", "unknown")
            client_ip = _get_client_ip(request)

            audit_security(
                AuditEventType.ERROR_VALIDATION,
                action="request_size_exceeded",
                request_id=request_id,
                source_ip=client_ip,
                details={
                    "content_length": content_length,
                    "max_allowed": max_size,
                    "path": request.url.path,
                },
            )

            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request entity too large",
                    "code": "request_too_large",
                    "max_size_mb": int(os.getenv("MAX_REQUEST_SIZE_MB", "10")),
                },
            )

        return await call_next(request)

    # Request timeout middleware (circuit breaker pattern - OWASP A04)
    @app.middleware("http")
    async def _request_timeout(request: Request, call_next) -> Response:
        """Apply request timeout for long-running operations."""
        import asyncio

        timeout_seconds = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))

        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            request_id = getattr(request.state, "request_id", "unknown")

            audit_security(
                AuditEventType.ERROR_SECURITY,
                action="request_timeout",
                request_id=request_id,
                source_ip=_get_client_ip(request),
                details={
                    "timeout_seconds": timeout_seconds,
                    "path": request.url.path,
                },
            )

            return JSONResponse(
                status_code=504,
                content={
                    "error": "Request timeout",
                    "code": "gateway_timeout",
                },
            )

    # Include routers
    for router in (
        auth_router,
        books_router,
        downloads_router,
        system_router,
        metrics_router,
    ):
        app.include_router(router)

    @app.get("/service-worker.js", include_in_schema=False)
    def _service_worker() -> Response:
        return _no_cache_response(_SW_UNREGISTER_SCRIPT, "application/javascript")

    @app.get("/app.js", include_in_schema=False)
    def _legacy_app_bundle() -> Response:
        return _no_cache_response(
            "window.location.replace('/');", "application/javascript"
        )

    @app.get("/style.css", include_in_schema=False)
    def _legacy_stylesheet() -> Response:
        return _no_cache_response("/* legacy fallback */", "text/css")

    @app.get("/favicon.ico", include_in_schema=False)
    def _favicon() -> Response:
        return Response(status_code=204)

    if FRONTEND_DIST.is_dir():
        app.mount(
            "/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend"
        )
    else:
        logger.warning("Frontend no encontrado en %s.", FRONTEND_DIST)

        @app.get("/", include_in_schema=False)
        def _no_frontend():
            return {
                "message": "Frontend build not found.",
                "hint": "Run `python -m launcher` or build the frontend into frontend/dist.",
            }

    return app


def _configure_stdio_utf8() -> None:
    """Fuerza UTF-8 en terminales Windows para evitar crashes de charmap."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


app = create_app()


def run_server() -> None:
    """Configura stdio e inicia la app con Uvicorn de forma estricta."""
    _configure_stdio_utf8()

    # Configure structured logging at startup
    configure_logging()

    host = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = os.getenv("PORT", "8000").strip()
    try:
        port = int(port_raw)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        logger.warning("PORT inválido=%r; usando 8000.", port_raw)
        port = 8000

    logger.info("Servidor iniciando en http://%s:%d", host, port)

    uvicorn.run("web.server:app", host=host, port=port)


def main() -> None:
    """Entrypoint del módulo: ``python -m web.server``."""
    run_server()


if __name__ == "__main__":
    main()
