import asyncio
from urllib.parse import quote, quote_plus

import config
from core.cache import (
    cached,
    get_book_metadata_cache,
    get_search_results_cache,
    invalidate_book_cache,
)

from .base import Plugin


class BookPlugin(Plugin):
    """Plugin for fetching book metadata and searching the catalog."""

    def __init__(self) -> None:
        super().__init__()
        self._book_cache = get_book_metadata_cache()
        self._search_cache = get_search_results_cache()

    async def fetch(self, book_id: str) -> dict:
        """Fetch book metadata with caching."""
        cache_key = f"book:{book_id}"

        # Try cache first
        cached = await self._book_cache.get(cache_key)
        if cached is not None:
            return cached

        async with asyncio.TaskGroup() as task_group:
            search_task = task_group.create_task(self._fetch_search(book_id))
            epub_task = task_group.create_task(self._fetch_epub(book_id))

        search_data = search_task.result()
        epub_data = epub_task.result()

        descriptions = epub_data.get("descriptions") or {}
        html_description = (
            descriptions.get("text/html", "") if isinstance(descriptions, dict) else ""
        )

        result = {
            "id": book_id,
            "ourn": epub_data.get("ourn"),
            "title": epub_data.get("title"),
            "authors": search_data.get("authors", []),
            "publishers": search_data.get("publishers", []),
            "description": html_description,
            "cover_url": search_data.get("cover_url"),
            "isbn": epub_data.get("isbn"),
            "language": epub_data.get("language", "en"),
            "publication_date": epub_data.get("publication_date"),
            "virtual_pages": epub_data.get("virtual_pages"),
            "chapters_url": epub_data.get("chapters"),
            "toc_url": epub_data.get("table_of_contents"),
            "spine_url": epub_data.get("spine"),
            "files_url": epub_data.get("files"),
        }

        # Cache the result
        await self._book_cache.set(cache_key, result)
        return result

    async def _fetch_search(self, book_id: str) -> dict:
        """Fetch book metadata from search API by book ID."""
        encoded_query = quote_plus(str(book_id).strip())
        url = f"{config.API_V2}/search/?query={encoded_query}&limit=3"
        data = await self.http.get_json(url)

        results = data.get("results", [])
        if not isinstance(results, list) or not results:
            return {}

        clean_book_id = str(book_id).strip()
        for result in results:
            if str(result.get("archive_id", "")) == clean_book_id:
                return result

        return results[0]

    async def _fetch_epub(self, book_id: str) -> dict:
        """Fetch EPUB metadata for a specific book ID."""
        encoded_book_id = quote(str(book_id).strip(), safe="")
        url = f"{config.API_V2}/epubs/urn:orm:book:{encoded_book_id}/"
        return await self.http.get_json(url)

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search for books with caching."""
        cache_key = f"search:{quote_plus(query.strip())}:{min(max(limit, 1), 100)}"

        # Try cache first
        cached = await self._search_cache.get(cache_key)
        if cached is not None:
            return cached

        encoded_query = quote_plus(str(query).strip())
        try:
            safe_limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            safe_limit = 10

        url = f"{config.API_V2}/search/?query={encoded_query}&limit={safe_limit}"
        data = await self.http.get_json(url)

        results = []
        raw_results = data.get("results", [])

        if not isinstance(raw_results, list):
            return results

        for item in raw_results:
            if item.get("content_format") != "book":
                continue
            results.append(
                {
                    "id": item.get("archive_id"),
                    "title": item.get("title"),
                    "authors": item.get("authors", []),
                    "cover_url": item.get("cover_url"),
                    "publishers": item.get("publishers", []),
                }
            )

        # Cache the results (shorter TTL for search)
        await self._search_cache.set(cache_key, results, ttl=300.0)  # 5 minutes
        return results

    async def invalidate_cache(self, book_id: str) -> int:
        """Invalidate all cached data for a book."""
        return await invalidate_book_cache(book_id)
