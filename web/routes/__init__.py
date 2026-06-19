"""API routers package."""

from web.routes.auth import router as auth_router
from web.routes.books import router as books_router
from web.routes.downloads import router as downloads_router
from web.routes.metrics import router as metrics_router
from web.routes.system import router as system_router

__all__ = [
    "auth_router",
    "books_router",
    "downloads_router",
    "metrics_router",
    "system_router",
]
