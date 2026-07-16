"""Book search and metadata routes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from core.cache import (
    get_book_metadata_cache,
    get_chapter_list_cache,
    get_search_results_cache,
)
from core.session_store import SessionStore
from web.api_utils import ErrorCode
from web.dependencies import get_kernel, get_session_store
from web.schemas import (
    BookChaptersResponse,
    BookInfoResponse,
    ChapterSummaryResponse,
    SearchResponse,
)

if TYPE_CHECKING:
    from core.kernel import Kernel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["books"])

MAX_SEARCH_LENGTH = 200


def _has_valid_cookies(store: SessionStore | None) -> tuple[bool, int]:
    """Return ``(has_cookies, count)`` for the given session store.

    A ``None`` store is treated as "no cookies available" so callers fail
    safely. Storage errors are swallowed into ``(False, 0)`` so transient
    issues don't crash the request — they surface as a 503 to the client.
    """
    if store is None:
        return False, 0
    try:
        count = store.count_stored_cookies()
    except Exception as exc:
        logger.warning("Failed to check cookies: %s", exc)
        return False, 0
    return count > 0, count


def _require_cookies(store: SessionStore, operation: str, book_id: str | None = None) -> None:
    """Raise 503 with a helpful message when no cookies are configured.

    Centralises the auth-required response so the three book routes stay
    consistent. ``operation`` is used in the log line; ``book_id`` is
    included in the log when relevant.
    """
    has_cookies, _ = _has_valid_cookies(store)
    if has_cookies:
        return
    detail = "Book " + book_id if book_id else operation
    logger.warning("%s attempted without cookies configured", detail)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "No session cookies configured. Please configure cookies first.",
            "code": ErrorCode.AUTH_REQUIRED,
            "suggestion": "Go to Settings > Cookies to configure your session cookies",
        },
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(
        default="",
        alias="q",
        description="Término de búsqueda. También acepta el alias 'query'.",
    ),
    query: str = Query(default="", include_in_schema=False),  # alias legacy, oculto en docs
    kernel: Kernel = Depends(get_kernel),
    session_store: SessionStore = Depends(get_session_store),
) -> SearchResponse:
    """Busca libros por título, autor o ISBN."""
    search_term = (q or query).strip()
    if not search_term:
        return SearchResponse(results=[])

    if len(search_term) > MAX_SEARCH_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Search term exceeds maximum length of {MAX_SEARCH_LENGTH} characters",
                "code": ErrorCode.BAD_REQUEST,
            },
        )

    _require_cookies(session_store, "Search")

    cache = get_search_results_cache()
    cache_key = f"search:{search_term.casefold()}"
    cached_results = await cache.get(cache_key)
    if cached_results is not None:
        return SearchResponse(results=cached_results)

    book_plugin = kernel["book"]
    try:
        results = await book_plugin.search(search_term)
        await cache.set(cache_key, results)
        return SearchResponse(results=results)
    except Exception as exc:
        logger.exception("Error searching for '%s'", search_term)
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
    kernel: Kernel = Depends(get_kernel),
    session_store: SessionStore = Depends(get_session_store),
) -> BookChaptersResponse:
    """Retorna la lista de capítulos de un libro."""
    _require_cookies(session_store, "Chapters fetch", book_id=book_id)

    cache = get_chapter_list_cache()
    cache_key = f"chapters:{book_id}"
    cached_chapters = await cache.get(cache_key)
    if cached_chapters is not None:
        return BookChaptersResponse.model_validate({"chapters": cached_chapters})

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
        logger.warning("Chapters fetch failed for book %s: %s", book_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": ErrorCode.BOOK_CHAPTERS_FAILED},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error fetching chapters for book %s", book_id)
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
        logger.warning("Datos de capítulo inválidos recibidos para %r: %s", book_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "Invalid chapter data returned by upstream service.",
                "code": ErrorCode.BOOK_CHAPTERS_FAILED,
            },
        ) from exc

    await cache.set(cache_key, [chapter.model_dump() for chapter in chapters])
    return BookChaptersResponse(chapters=chapters)


@router.get("/book/{book_id}", response_model=BookInfoResponse)
async def book_info(
    book_id: str,
    kernel: Kernel = Depends(get_kernel),
    session_store: SessionStore = Depends(get_session_store),
) -> BookInfoResponse:
    """Retorna los metadatos de un libro por su ID."""
    _require_cookies(session_store, "Book info fetch", book_id=book_id)

    cache = get_book_metadata_cache()
    cache_key = f"book:{book_id}"
    cached_book = await cache.get(cache_key)
    if cached_book is not None:
        return BookInfoResponse.model_validate(cached_book)

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

    response = BookInfoResponse.model_validate(result)
    await cache.set(cache_key, response.model_dump())
    return response
