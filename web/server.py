"""FastAPI application factory and server entry point for Ryliox.

The ``create_app`` factory wires every router declared in
:mod:`web.routes` to a single :class:`fastapi.FastAPI` instance, registers
middleware (CORS, security headers, trusted hosts, request size limits) and
attaches the application-scoped kernel, session store and download queue to
``app.state`` during startup.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import config
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
    from pathlib import Path

logger = logging.getLogger(__name__)


# ─── Security headers middleware ────────────────────────────────────────────


def _security_headers_middleware_factory():
    async def _middleware(request: Request, call_next):
        if not config.SETTINGS.security.enable_security_headers:
            return await call_next(request)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
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


def _sanitize_errors(errors: list[dict]) -> list[dict]:
    """Strip non-JSON-serializable values from Pydantic validation errors."""
    safe: list[dict] = []
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


def _request_size_middleware_factory(max_bytes: int):
    async def _middleware(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"error": "Request body too large", "code": ErrorCode.BAD_REQUEST},
            )
        return await call_next(request)

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
    app.middleware("http")(
        _request_size_middleware_factory(settings.security.max_request_size_mb * 1024 * 1024)
    )

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
    async def _validation_handler(request: Request, exc: RequestValidationError):
        logger.debug("Validation error: %s", exc.errors())
        errors = _sanitize_errors(exc.errors())
        return error_response(
            "Request validation failed",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.BAD_REQUEST,
            details={"errors": errors},
        )

    @app.exception_handler(ForbiddenOriginError)
    async def _forbidden_origin_handler(request: Request, exc: ForbiddenOriginError):
        logger.warning("Cross-origin request blocked: %s", exc)
        return error_response(
            f"Cross-origin request blocked for '{exc.args[0]}'.",
            status.HTTP_403_FORBIDDEN,
            code=ErrorCode.CROSS_ORIGIN_BLOCKED,
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
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
        app.mount(
            "/assets",
            StaticFiles(directory=frontend_dist / "_astro", check_dir=False),
            name="frontend-assets",
        )
        mounted.append(frontend_dist)
    if legacy_static.is_dir():
        app.mount("/static", StaticFiles(directory=legacy_static), name="legacy-static")
        mounted.append(legacy_static)

    if not mounted:
        return

    @app.get("/", include_in_schema=False)
    async def _root_index() -> object:
        from fastapi.responses import FileResponse

        for candidate in (frontend_dist / "index.html", legacy_static / "index.html"):
            if candidate.is_file():
                return FileResponse(candidate)
        return JSONResponse({"name": "Ryliox", "status": "running"})


# ─── Entrypoint ──────────────────────────────────────────────────────────────


app = create_app()


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Run the Uvicorn server (used by ``main.py`` and the launcher)."""
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
