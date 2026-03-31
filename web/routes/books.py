"""Book search and metadata routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from core.kernel import Kernel
from core.session_store import SessionStore
from web.api_utils import ErrorCode
from web.dependencies import get_kernel
from web.schemas import (
    BookChaptersResponse,
    BookInfoResponse,
    ChapterSummaryResponse,
    SearchResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["books"])

MAX_SEARCH_LENGTH = 200


def _has_valid_cookies() -> tuple[bool, int]:
    """Check if valid cookies are configured."""
    try:
        store = SessionStore()
        count = store._count_stored_cookies()
        return count > 0, count
    except Exception as e:
        logger.warning(f"Failed to check cookies: {e}")
        return False, 0


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(
        default="",
        alias="q",
        description="Término de búsqueda. También acepta el alias 'query'.",
    ),
    query: str = Query(
        default="", include_in_schema=False
    ),  # alias legacy, oculto en docs
    kernel: Kernel = Depends(get_kernel),
) -> SearchResponse:
    """Busca libros por título, autor o ISBN."""
    search_term = (q or query).strip()
    if not search_term:
        return SearchResponse(results=[])

    if len(search_term) > MAX_SEARCH_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Search term exceeds maximum length of {MAX_SEARCH_LENGTH} characters.",
                "code": ErrorCode.BAD_REQUEST,
            },
        )

    # Check if cookies are configured
    has_cookies, cookie_count = _has_valid_cookies()
    if not has_cookies:
        logger.warning(f"Search attempted without cookies configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "No session cookies configured. Please configure cookies first.",
                "code": ErrorCode.AUTH_REQUIRED,
                "suggestion": "Go to Settings > Cookies to configure your session cookies",
            },
        )

    book_plugin = kernel["book"]
    try:
        results = await book_plugin.search(search_term)
        return SearchResponse(results=results)
    except Exception as exc:
        logger.exception(f"Error searching for '{search_term}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "Failed to search books. The external service may be unavailable.",
                "code": ErrorCode.SEARCH_FAILED,
                "details": str(exc) if str(exc) else None,
            },
        ) from exc


@router.get("/book/{book_id}/chapters", response_model=BookChaptersResponse)
async def book_chapters(
    book_id: str,
    request: Request,
    kernel: Kernel = Depends(get_kernel),
) -> BookChaptersResponse:
    """Retorna la lista de capítulos de un libro."""

    # Check if cookies are configured first
    has_cookies, cookie_count = _has_valid_cookies()
    if not has_cookies:
        logger.warning(f"Chapters fetch attempted without cookies for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "No session cookies configured. Please configure cookies first.",
                "code": ErrorCode.AUTH_REQUIRED,
                "suggestion": "Go to Settings > Cookies to configure your session cookies",
            },
        )

    # Verify chapters plugin is available
    try:
        chapters_plugin = kernel["chapters"]
    except KeyError:
        logger.error("Chapters plugin not registered in kernel")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Chapters service unavailable",
                "code": ErrorCode.INTERNAL_ERROR,
            },
        )

    try:
        raw_chapters: list[dict] = await chapters_plugin.fetch_list(book_id)
    except (LookupError, ValueError) as exc:
        logger.warning(f"Chapters fetch failed for book {book_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": ErrorCode.BOOK_CHAPTERS_FAILED},
        ) from exc
    except Exception as exc:
        logger.exception(
            f"Unexpected error fetching chapters for book {book_id}: {exc}"
        )
        # Log additional context for debugging
        logger.error(f"Exception type: {type(exc).__name__}")
        logger.error(f"Exception args: {getattr(exc, 'args', 'N/A')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": f"Unexpected error fetching chapters: {type(exc).__name__}",
                "code": ErrorCode.INTERNAL_ERROR,
                "details": str(exc) if str(exc) else None,
            },
        ) from exc

    try:
        chapters = []
        for idx, chapter in enumerate(raw_chapters):
            raw_index = chapter.get("index", idx)
            raw_pages = chapter.get("virtual_pages")
            raw_minutes = chapter.get("minutes_required")

            pages = int(raw_pages) if raw_pages is not None else None
            if pages is not None and pages <= 0:
                pages = None

            minutes = float(raw_minutes) if raw_minutes is not None else None
            if minutes is not None and minutes < 0:
                minutes = None

            chapters.append(
                ChapterSummaryResponse(
                    index=int(raw_index),
                    title=str(chapter.get("title") or f"Chapter {idx + 1}"),
                    pages=pages,
                    minutes=minutes,
                )
            )
    except (TypeError, ValueError, ValidationError) as exc:
        logger.warning(
            "Datos de capitulo invalidos recibidos para %r: %s", book_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "Invalid chapter data returned by upstream service.",
                "code": ErrorCode.BOOK_CHAPTERS_FAILED,
            },
        ) from exc

    return BookChaptersResponse(chapters=chapters)


@router.get("/book/{book_id}", response_model=BookInfoResponse)
async def book_info(
    book_id: str,
    kernel: Kernel = Depends(get_kernel),
) -> BookInfoResponse:
    """Retorna los metadatos de un libro por su ID."""

    # Check if cookies are configured
    has_cookies, cookie_count = _has_valid_cookies()
    if not has_cookies:
        logger.warning(f"Book info fetch attempted without cookies for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "No session cookies configured. Please configure cookies first.",
                "code": ErrorCode.AUTH_REQUIRED,
                "suggestion": "Go to Settings > Cookies to configure your session cookies",
            },
        )

    book_plugin = kernel["book"]
    try:
        result = await book_plugin.fetch(book_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(exc), "code": ErrorCode.BOOK_FETCH_FAILED},
        ) from exc
    except Exception as exc:
        logger.exception("Error inesperado al obtener libro %r.", book_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Unexpected error fetching book.",
                "code": ErrorCode.INTERNAL_ERROR,
            },
        ) from exc

    return BookInfoResponse.model_validate(result)
