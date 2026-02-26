"""FastAPI web server."""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

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

_CORS_ORIGINS: Final[list[str]] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
]

_NO_CACHE_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

_SW_UNREGISTER_SCRIPT: Final[
    str
] = """\
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


def _no_cache_response(content: str, media_type: str) -> Response:
    """Devuelve una respuesta con cabeceras que deshabilitan el caché."""
    return Response(content=content, media_type=media_type, headers=_NO_CACHE_HEADERS)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Inicializa y apaga ordenadamente todos los servicios de la app."""
    app.state.started_at = time.monotonic()
    app.state.app_version = APP_VERSION
    initialize_app_services(app)
    logger.info("App v%s iniciada.", APP_VERSION)
    try:
        yield
    finally:
        await shutdown_app_services(app)
        logger.info("App apagada correctamente.")


def create_app() -> FastAPI:
    """Construye la aplicación FastAPI con rutas API y hosting de estáticos."""
    from web.routes.auth import router as auth_router
    from web.routes.books import router as books_router
    from web.routes.downloads import router as downloads_router
    from web.routes.system import router as system_router

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ForbiddenOriginError)
    async def _handle_forbidden_origin(
        _: Request, exc: ForbiddenOriginError
    ) -> Response:
        return error_response(str(exc), exc.http_status, code="forbidden_origin")

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

    for router in (auth_router, books_router, downloads_router, system_router):
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
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

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
