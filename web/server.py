"""FastAPI application factory and server entry point for Ryliox.

The ``create_app`` factory wires every router declared in
:mod:`web.routes` to a single :class:`fastapi.FastAPI` instance, registers
middleware (CORS, security headers, trusted hosts, request size limits) and
attaches the application-scoped kernel, session store and download queue to
``app.state`` during startup.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import logging
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

import config
from core.logging_config import configure_logging
from core.metrics import metrics
from web.api_utils import ErrorCode, error_response
from web.dependencies import (
    ForbiddenOriginError,
    initialize_app_services,
    shutdown_app_services,
)
from web.routes import (
    auth_router,
    books_router,
    downloads_router,
    metrics_router,
    system_router,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

_FRONTEND_STATIC_DIRS: tuple[str, ...] = ("_astro", "icons", "locales")
_RESERVED_FRONTEND_PREFIXES: tuple[str, ...] = ("api", "metrics")

_RATE_LIMITED_ENDPOINTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/cookies"),
        ("POST", "/api/download"),
        ("POST", "/api/cancel"),
        ("POST", "/api/reveal"),
        ("POST", "/api/settings/output-dir"),
    }
)


class _RateLimiter:
    """Small in-memory fixed-window limiter keyed by client IP and endpoint."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._requests: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def is_allowed(self, client_ip: str, endpoint: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        key = (client_ip, endpoint)

        with self._lock:
            if now - self._last_cleanup >= self.window_seconds:
                self._clear_old_entries(cutoff)
                self._last_cleanup = now
            timestamps = [ts for ts in self._requests[key] if ts > cutoff]
            if len(timestamps) >= self.max_requests:
                self._requests[key] = timestamps
                return False

            timestamps.append(now)
            self._requests[key] = timestamps
            return True

    def clear_old_entries(self) -> None:
        cutoff = time.monotonic() - self.window_seconds
        with self._lock:
            self._clear_old_entries(cutoff)
            self._last_cleanup = time.monotonic()

    def _clear_old_entries(self, cutoff: float) -> None:
        stale_keys = []
        for key, timestamps in self._requests.items():
            fresh = [ts for ts in timestamps if ts > cutoff]
            if fresh:
                self._requests[key] = fresh
            else:
                stale_keys.append(key)
        for key in stale_keys:
            self._requests.pop(key, None)


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _is_loopback_bind(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _validate_deployment_security() -> None:
    settings = config.SETTINGS
    remote = not _is_loopback_bind(settings.server.host)
    token = settings.security.admin_token
    remote_requires_auth = remote and not settings.security.allow_unauthenticated_local_proxy
    if (remote_requires_auth or settings.security.environment == "production") and (
        token is None or len(token) < 32
    ):
        raise RuntimeError(
            "Remote/production API requires RYLIOX_SECURITY__ADMIN_TOKEN (at least 32 characters)"
        )
    if settings.security.environment == "production" and not settings.session.encryption_key:
        key_file = settings.session.encryption_key_file
        if key_file is None or not Path(key_file).expanduser().is_file():
            raise RuntimeError(
                "Production requires RYLIOX_SESSION__ENCRYPTION_KEY or an existing "
                "RYLIOX_SESSION__ENCRYPTION_KEY_FILE"
            )
    if settings.security.environment == "production" and not settings.audit.hmac_key:
        audit_key_file = settings.audit.hmac_key_file
        if audit_key_file is None or not Path(audit_key_file).expanduser().is_file():
            raise RuntimeError(
                "Production requires RYLIOX_AUDIT__HMAC_KEY or an existing "
                "RYLIOX_AUDIT__HMAC_KEY_FILE"
            )


def _admin_session_value(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"ryliox-admin-session", hashlib.sha256).hexdigest()


NextHandler = Callable[[Request], Awaitable[Response]]
MiddlewareHandler = Callable[[Request, NextHandler], Awaitable[Response]]


def _request_id_middleware_factory() -> MiddlewareHandler:
    async def _middleware(request: Request, call_next: NextHandler) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    return _middleware


def _rate_limit_middleware_factory(limiter: _RateLimiter) -> MiddlewareHandler:
    async def _middleware(request: Request, call_next: NextHandler) -> Response:
        key = (request.method.upper(), request.url.path)
        if key in _RATE_LIMITED_ENDPOINTS and not limiter.is_allowed(
            _client_ip(request), request.url.path
        ):
            with suppress(Exception):
                metrics.record_rate_limit_hit(request.url.path)
            return error_response(
                "Too many requests",
                status.HTTP_429_TOO_MANY_REQUESTS,
                code=ErrorCode.RATE_LIMITED,
                details={"retry_after_seconds": limiter.window_seconds},
            )
        return await call_next(request)

    return _middleware


def _admin_auth_middleware_factory() -> MiddlewareHandler:
    async def _middleware(request: Request, call_next: NextHandler) -> Response:
        if not request.url.path.startswith(("/api", "/metrics")):
            return await call_next(request)
        if request.url.path in {"/api/health", "/api/admin/session"}:
            return await call_next(request)
        if (
            _is_loopback_bind(config.SETTINGS.server.host)
            or config.SETTINGS.security.allow_unauthenticated_local_proxy
        ):
            return await call_next(request)
        configured = config.SETTINGS.security.admin_token or ""
        authorization = request.headers.get("authorization", "")
        scheme, _, provided = authorization.partition(" ")
        bearer_valid = scheme.lower() == "bearer" and hmac.compare_digest(provided, configured)
        session_valid = hmac.compare_digest(
            request.cookies.get("ryliox_admin_session", ""),
            _admin_session_value(configured),
        )
        if not bearer_valid and not session_valid:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Administrative authentication required",
                    "code": "admin_auth_required",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)

    return _middleware


# ─── Security headers middleware ────────────────────────────────────────────


def _security_headers_middleware_factory() -> MiddlewareHandler:
    async def _middleware(request: Request, call_next: NextHandler) -> Response:
        if not config.SETTINGS.security.enable_security_headers:
            return await call_next(request)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if config.SETTINGS.security.csp_policy:
            response.headers.setdefault(
                "Content-Security-Policy", config.SETTINGS.security.csp_policy
            )
        if config.SETTINGS.security.enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={config.SETTINGS.security.hsts_max_age}; includeSubDomains",
            )
        return response

    return _middleware


# ─── Error sanitisation ─────────────────────────────────────────────────────


def _sanitize_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Strip non-JSON-serializable values from Pydantic validation errors."""
    safe: list[dict[str, Any]] = []
    for err in errors:
        item = dict(err)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            item["ctx"] = {
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in ctx.items()
            }
        safe.append(item)
    return safe


# ─── Request size / timeout middleware ───────────────────────────────────────


class RequestBodyLimitMiddleware:
    """Bound request bodies even when clients use chunked transfer encoding."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length", b"")
        if content_length.isdigit() and int(content_length) > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        messages: list[Message] = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                return
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break

        async def replay() -> Message:
            if messages:
                return messages.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"error": "Request body too large", "code": ErrorCode.REQUEST_TOO_LARGE},
        )
        await response(scope, receive, send)


def _timeout_and_metrics_middleware_factory(timeout_seconds: float) -> MiddlewareHandler:
    async def _middleware(request: Request, call_next: NextHandler) -> Response:
        started = time.monotonic()
        try:
            async with asyncio.timeout(timeout_seconds):
                response = await call_next(request)
        except TimeoutError:
            response = JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"error": "Request timed out", "code": "request_timeout"},
            )
        with suppress(Exception):
            route = request.scope.get("route")
            metrics.record_http_request(
                request.method,
                route.path if route is not None else request.url.path,
                response.status_code,
                time.monotonic() - started,
            )
        return response

    return _middleware


# ─── Lifespan ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.started_at = time.monotonic()
    app.state.app_version = config.SETTINGS.server.app_version
    await initialize_app_services(app)
    logger.info("Ryliox ready on %s:%d", config.SETTINGS.server.host, config.SETTINGS.server.port)
    try:
        yield
    finally:
        await shutdown_app_services(app)


# ─── Application factory ─────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A fully configured :class:`fastapi.FastAPI` instance.
    """
    _validate_deployment_security()
    settings = config.SETTINGS
    is_prod = settings.security.environment == "production"

    app = FastAPI(
        title="Ryliox",
        version=settings.server.app_version,
        description="O'Reilly Learning Platform book downloader.",
        docs_url=None if is_prod else "/api/docs",
        redoc_url=None if is_prod else "/api/redoc",
        openapi_url=None if is_prod else "/api/openapi.json",
        lifespan=_lifespan,
    )
    app.state.rate_limiter = _RateLimiter(
        settings.rate_limit.max_requests,
        settings.rate_limit.window_seconds,
    )

    # ── Middleware ──
    if is_prod and settings.security.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.security.allowed_hosts,
        )

    if settings.security.cors_origins and settings.security.cors_origins != ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.security.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    app.middleware("http")(_security_headers_middleware_factory())
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=settings.security.max_request_size_mb * 1024 * 1024,
    )
    app.middleware("http")(
        _timeout_and_metrics_middleware_factory(settings.http.request_timeout_seconds)
    )
    app.middleware("http")(_admin_auth_middleware_factory())
    app.middleware("http")(_rate_limit_middleware_factory(app.state.rate_limiter))
    app.middleware("http")(_request_id_middleware_factory())

    @app.post("/api/admin/session", include_in_schema=False)
    async def _create_admin_session(request: Request) -> Response:
        configured = settings.security.admin_token or ""
        if not configured:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "Administrative authentication is not configured"},
            )
        try:
            payload = await request.json()
        except ValueError:
            payload = {}
        provided = payload.get("token", "") if isinstance(payload, dict) else ""
        if not isinstance(provided, str) or not hmac.compare_digest(provided, configured):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid administrative token", "code": "admin_auth_invalid"},
            )
        response = JSONResponse({"success": True})
        response.set_cookie(
            "ryliox_admin_session",
            _admin_session_value(configured),
            httponly=True,
            secure=settings.security.environment == "production",
            samesite="strict",
            path="/",
        )
        return response

    # ── Routers ──
    app.include_router(auth_router)
    app.include_router(books_router)
    app.include_router(downloads_router)
    app.include_router(metrics_router)
    app.include_router(system_router)

    # ── Static / SPA ──
    _mount_static(app)

    # ── Exception handlers ──
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.debug("Validation error: %s", exc.errors())
        errors = _sanitize_errors(exc.errors())
        return error_response(
            "Request validation failed",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.BAD_REQUEST,
            details={"errors": errors},
        )

    @app.exception_handler(ForbiddenOriginError)
    async def _forbidden_origin_handler(
        request: Request, exc: ForbiddenOriginError
    ) -> JSONResponse:
        logger.warning("Cross-origin request blocked: %s", exc)
        return error_response(
            f"Cross-origin request blocked for '{exc.args[0]}'.",
            status.HTTP_403_FORBIDDEN,
            code=ErrorCode.CROSS_ORIGIN_BLOCKED,
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return error_response(
            "Internal server error",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
        )

    return app


def _mount_static(app: FastAPI) -> None:
    """Mount static asset directories, preferring the modern Astro build."""
    frontend_dist: Path = config.REPO_ROOT / "frontend" / "dist"
    legacy_static: Path = config.REPO_ROOT / "web" / "static"

    mounted: list[Path] = []
    if frontend_dist.is_dir():
        for directory_name in _FRONTEND_STATIC_DIRS:
            directory = frontend_dist / directory_name
            if directory.is_dir():
                app.mount(
                    f"/{directory_name}",
                    StaticFiles(directory=directory, check_dir=False),
                    name=f"frontend-{directory_name}",
                )
        mounted.append(frontend_dist)
    if legacy_static.is_dir():
        app.mount("/static", StaticFiles(directory=legacy_static), name="legacy-static")
        mounted.append(legacy_static)

    if not mounted:
        return

    @app.get("/{path:path}", include_in_schema=False)
    async def _frontend_entry(path: str) -> object:
        if _is_reserved_frontend_path(path):
            return JSONResponse({"detail": "Not Found"}, status_code=status.HTTP_404_NOT_FOUND)

        if frontend_dist.is_dir():
            candidate = _safe_static_file(frontend_dist, path)
            if candidate and candidate.is_file():
                return FileResponse(candidate)

            index = frontend_dist / "index.html"
            if index.is_file():
                return FileResponse(index)

        legacy_index = legacy_static / "index.html"
        if legacy_index.is_file():
            return FileResponse(legacy_index)

        return JSONResponse({"name": "Ryliox", "status": "running"})


def _is_reserved_frontend_path(path: str) -> bool:
    first_segment = path.strip("/").split("/", 1)[0]
    return first_segment in _RESERVED_FRONTEND_PREFIXES


def _safe_static_file(root: Path, path: str) -> Path | None:
    if not path:
        return None

    root = root.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


# ─── Entrypoint ──────────────────────────────────────────────────────────────


app = create_app()


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Run the Uvicorn server (used by ``main.py`` and the launcher)."""
    configure_logging(
        level=config.SETTINGS.logging.level,
        json_format=config.SETTINGS.logging.json_logs,
    )
    uvicorn.run(
        "web.server:app",
        host=host or config.SETTINGS.server.host,
        port=port or config.SETTINGS.server.port,
        reload=False,
        log_level=config.SETTINGS.logging.level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    run_server()
