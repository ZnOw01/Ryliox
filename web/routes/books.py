"""Book search and metadata routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from core.kernel import Kernel
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

    book_plugin = kernel["book"]
    results = await book_plugin.search(search_term)
    return SearchResponse(results=results)


@router.get("/book/{book_id}/chapters", response_model=BookChaptersResponse)
async def book_chapters(
    book_id: str,
    kernel: Kernel = Depends(get_kernel),
) -> BookChaptersResponse:
    """Retorna la lista de capítulos de un libro."""
    chapters_plugin = kernel["chapters"]
    try:
        raw_chapters: list[dict] = await chapters_plugin.fetch_list(book_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": ErrorCode.BOOK_CHAPTERS_FAILED},
        ) from exc
    except Exception as exc:
        logger.exception("Error inesperado al obtener capítulos de %r.", book_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Unexpected error fetching chapters.",
                "code": ErrorCode.INTERNAL_ERROR,
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
        logger.warning("Datos de capitulo invalidos recibidos para %r: %s", book_id, exc)
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
