import asyncio
from urllib.parse import quote, quote_plus, urlparse

from bs4 import BeautifulSoup

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

        if value.startswith(("http://", "https://")):
            try:
                parsed = urlparse(value)
            except ValueError:
                return None
            parts = [part for part in parsed.path.split("/") if part]
            if parts:
                return parts[-1]

        if " " in value:
            return None

        if "/" not in value and "\\" not in value:
            return value

        return None

    async def fetch(self, book_id: str) -> dict:
        search_result, epub_result = await asyncio.gather(
            self._fetch_search(book_id),
            self._fetch_epub(book_id),
            return_exceptions=True,
        )

        search_data = search_result if isinstance(search_result, dict) else {}
        epub_data = epub_result if isinstance(epub_result, dict) else {}

        fallback_metadata = await self._fetch_epub_fallback_metadata(
            book_id,
            missing_fields={
                "authors": not search_data.get("authors"),
                "publishers": not search_data.get("publishers"),
                "cover_url": not search_data.get("cover_url"),
            },
        )

        descriptions = epub_data.get("descriptions") or {}
        html_description = (
            descriptions.get("text/html", "") if isinstance(descriptions, dict) else ""
        )

        result = {
            "id": book_id,
            "ourn": epub_data.get("ourn"),
            "title": epub_data.get("title"),
            "authors": search_data.get("authors") or fallback_metadata.get("authors", []),
            "publishers": search_data.get("publishers") or fallback_metadata.get("publishers", []),
            "description": html_description,
            "cover_url": search_data.get("cover_url") or fallback_metadata.get("cover_url"),
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

    async def _fetch_epub_fallback_metadata(
        self,
        book_id: str,
        *,
        missing_fields: dict[str, bool],
    ) -> dict:
        if not any(missing_fields.values()):
            return {}

        async with asyncio.TaskGroup() as task_group:
            titlepage_task = (
                task_group.create_task(self._fetch_epub_file(book_id, "titlepage01.html"))
                if missing_fields.get("authors")
                else None
            )
            copyright_task = (
                task_group.create_task(self._fetch_epub_file(book_id, "copyright-page01.html"))
                if missing_fields.get("authors") or missing_fields.get("publishers")
                else None
            )
            cover_task = (
                task_group.create_task(self._fetch_epub_file(book_id, "cover.html"))
                if missing_fields.get("cover_url")
                else None
            )

        titlepage_html = titlepage_task.result() if titlepage_task else ""
        copyright_html = copyright_task.result() if copyright_task else ""
        cover_html = cover_task.result() if cover_task else ""

        authors = self._extract_authors_from_epub_pages(
            titlepage_html=titlepage_html,
            copyright_html=copyright_html,
        )
        publishers = self._extract_publishers_from_epub_page(copyright_html)
        cover_url = self._extract_cover_url_from_epub_page(book_id, cover_html)

        return {
            "authors": authors,
            "publishers": publishers,
            "cover_url": cover_url,
        }

    async def _fetch_epub_file(self, book_id: str, relative_path: str) -> str:
        encoded_book_id = quote(str(book_id).strip(), safe="")
        encoded_path = quote(relative_path, safe="/")
        url = f"{config.API_V2}/epubs/urn:orm:book:{encoded_book_id}/files/{encoded_path}"
        try:
            return await self.http.get_text(url)
        except Exception:
            return ""

    def _extract_authors_from_epub_pages(
        self,
        *,
        titlepage_html: str,
        copyright_html: str,
    ) -> list[str]:
        for html in (titlepage_html, copyright_html):
            authors = self._extract_authors_from_html(html)
            if authors:
                return authors
        return []

    def _extract_authors_from_html(self, html: str) -> list[str]:
        if not html.strip():
            return []

        soup = BeautifulSoup(html, "html.parser")
        author_nodes = soup.select(".author")
        candidates: list[str] = []

        for node in author_nodes:
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            normalized = text.removeprefix("por ").strip()
            normalized = normalized.replace(" y ", ", ")
            parts = [part.strip(" ,") for part in normalized.split(",") if part.strip(" ,")]
            candidates.extend(parts)

        deduped: list[str] = []
        for name in candidates:
            if name not in deduped:
                deduped.append(name)
        return deduped

    def _extract_publishers_from_epub_page(self, html: str) -> list[str]:
        if not html.strip():
            return []

        soup = BeautifulSoup(html, "html.parser")
        publishers: list[str] = []

        for node in soup.select(".publishername"):
            value = node.get_text(" ", strip=True).strip(" ,")
            if value and value not in publishers:
                publishers.append(value)

        return publishers

    def _extract_cover_url_from_epub_page(self, book_id: str, html: str) -> str | None:
        if html.strip():
            soup = BeautifulSoup(html, "html.parser")
            image = soup.find("img")
            if image and image.get("src"):
                raw_src = str(image["src"]).strip()
                if raw_src.startswith(("http://", "https://")):
                    return raw_src
                return f"{config.BASE_URL}{raw_src}" if raw_src.startswith("/") else f"{config.BASE_URL}/{raw_src}"

        clean_book_id = str(book_id).strip()
        if clean_book_id:
            return f"{config.BASE_URL}/library/cover/{clean_book_id}/"
        return None

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
