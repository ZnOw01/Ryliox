import asyncio
from urllib.parse import quote, quote_plus

import config

from .base import Plugin


class BookPlugin(Plugin):
    """Plugin for fetching book metadata and searching the catalog."""

    async def fetch(self, book_id: str) -> dict:
        search_task = asyncio.create_task(self._fetch_search(book_id))
        epub_task = asyncio.create_task(self._fetch_epub(book_id))

        search_data, epub_data = await asyncio.gather(search_task, epub_task)

        descriptions = epub_data.get("descriptions") or {}
        html_description = (
            descriptions.get("text/html", "") if isinstance(descriptions, dict) else ""
        )

        return {
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

    async def _fetch_search(self, book_id: str) -> dict:
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
        encoded_book_id = quote(str(book_id).strip(), safe="")
        url = f"{config.API_V2}/epubs/urn:orm:book:{encoded_book_id}/"
        return await self.http.get_json(url)

    async def search(self, query: str, limit: int = 10) -> list[dict]:
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

        return results
