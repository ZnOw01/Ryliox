"""Book metadata plugin: search O'Reilly and fetch per-book EPUB details."""

from __future__ import annotations

import re
from urllib.parse import quote

import config

from .base import Plugin

_COVER_WIDTH_RE = re.compile(r"/\d+w/?$")
_HIGH_RES_COVER_WIDTH = "1200w"


def _upgrade_cover_url(url: str) -> str:
    """Upgrade an O'Reilly cover URL to a high-resolution variant.

    O'Reilly serves covers at /library/cover/{isbn}/ and /covers/urn:orm:book:{id}/,
    optionally with a /{N}w/ width segment. The base URL (no width) returns a
    low-res thumbnail (~160x184). Appending /1200w/ returns a print-quality image.
    """
    if "/library/cover/" not in url and "/covers/urn:orm:book:" not in url:
        return url
    stripped = _COVER_WIDTH_RE.sub("", url, count=1).rstrip("/")
    return f"{stripped}/{_HIGH_RES_COVER_WIDTH}/"


class BookPlugin(Plugin):
    async def fetch(self, book_id: str) -> dict:
        search_data = await self._fetch_search(book_id)
        epub_data = await self._fetch_epub(book_id)

        authors = list(search_data.get("authors", []))
        publishers = list(search_data.get("publishers", []))
        cover_url = search_data.get("cover_url")

        # When the search API returns no metadata, fall back to scraping the
        # EPUB's titlepage / copyright page / cover. The O'Reilly backend no
        # longer populates these fields in the search index for every book.
        if not (authors and publishers and cover_url):
            file_authors, file_publishers, file_cover = await self._extract_epub_metadata(book_id)
            if not authors and file_authors:
                authors = file_authors
            if not publishers and file_publishers:
                publishers = file_publishers
            if not cover_url and file_cover:
                cover_url = file_cover

        if not cover_url and book_id:
            cover_url = f"https://learning.oreilly.com/library/cover/{book_id}/"
        if cover_url:
            cover_url = _upgrade_cover_url(cover_url)

        return {
            "id": book_id,
            "ourn": epub_data.get("ourn", ""),
            "title": epub_data.get("title") or "Unknown",
            "authors": authors or epub_data.get("authors", []),
            "publishers": publishers or epub_data.get("publishers", []),
            "description": (epub_data.get("descriptions") or {}).get("text/html", ""),
            "cover_url": cover_url,
            "isbn": epub_data.get("isbn", ""),
            "language": epub_data.get("language", "en"),
            "publication_date": epub_data.get("publication_date", ""),
            "virtual_pages": epub_data.get("virtual_pages"),
            "chapters_url": epub_data.get("chapters"),
            "toc_url": epub_data.get("table_of_contents"),
            "spine_url": epub_data.get("spine"),
            "files_url": epub_data.get("files"),
        }

    async def _extract_epub_metadata(self, book_id: str) -> tuple[list[str], list[str], str | None]:
        """Scrape sparse metadata from the EPUB's static HTML files."""
        authors: list[str] = []
        publishers: list[str] = []
        cover_url: str | None = None
        try:
            title_html = await self._fetch_epub_file(book_id, "titlepage01.html")
            for match in re.finditer(r'<p class="author">([^<]+)</p>', title_html):
                raw = match.group(1).strip()
                # Split on the Spanish/English " y " conjunction, then split
                # any remaining "Last, First" pairs on commas.
                authors = []
                for chunk in re.split(r"\s+y\s+", raw):
                    for sub in chunk.split(","):
                        sub = sub.strip()
                        if sub:
                            authors.append(sub)
        except Exception:
            pass
        try:
            copyright_html = await self._fetch_epub_file(book_id, "copyright-page01.html")
            for match in re.finditer(r'<span class="publishername">([^<]+)</span>', copyright_html):
                publishers = [match.group(1).strip()]
        except Exception:
            pass
        try:
            cover_html = await self._fetch_epub_file(book_id, "cover.html")
            for match in re.finditer(r'<img\s+src="([^"]+)"', cover_html):
                src = match.group(1)
                if not src.startswith("http"):
                    src = f"https://learning.oreilly.com{src}"
                cover_url = src
                break
        except Exception:
            pass
        return authors, publishers, cover_url

    async def _fetch_search(self, book_id: str) -> dict:
        url = f"{config.API_V2}/search/?query={quote(book_id, safe='')}&limit=1"
        data = await self.http.get_json(url)
        results = data.get("results", [])
        if results:
            return results[0]
        if book_id.isdigit() or book_id.startswith("urn:orm:book:"):
            try:
                epub_data = await self._fetch_epub(book_id)
                if epub_data and epub_data.get("title"):
                    return {
                        "id": book_id,
                        "archive_id": book_id,
                        "title": epub_data.get("title"),
                        "authors": epub_data.get("authors", []),
                        "cover_url": f"https://learning.oreilly.com/library/cover/{book_id}/",
                        "publishers": epub_data.get("publishers", []),
                        "content_format": epub_data.get("content_format", "book"),
                    }
            except Exception:
                pass
        return {}

    async def _fetch_epub(self, book_id: str) -> dict:
        url = f"{config.API_V2}/epubs/urn:orm:book:{book_id}/"
        return await self.http.get_json(url)

    async def _fetch_epub_file(self, book_id: str, relative_path: str) -> str:
        url = f"{config.API_V2}/epubs/urn:orm:book:{book_id}/files/{quote(relative_path, safe='/')}"
        return await self.http.get_text(url)

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        url = f"{config.API_V2}/search/?query={quote(query, safe='')}&limit={limit}"
        data = await self.http.get_json(url)
        results = []
        for item in data.get("results", []):
            fmt = item.get("content_format", "")
            if isinstance(fmt, str) and fmt and "book" not in fmt.lower():
                continue

            book_id = item.get("archive_id") or item.get("id")
            if not book_id:
                continue

            results.append(
                {
                    "id": book_id,
                    "title": item.get("title"),
                    "authors": item.get("authors", []),
                    "cover_url": item.get("cover_url"),
                    "publishers": item.get("publishers", []),
                }
            )

        if not results and (query.isdigit() or query.startswith("urn:orm:book:")):
            try:
                epub_data = await self._fetch_epub(query)
                if epub_data and epub_data.get("title"):
                    results.append(
                        {
                            "id": query,
                            "title": epub_data.get("title"),
                            "authors": epub_data.get("authors", []),
                            "cover_url": f"https://learning.oreilly.com/library/cover/{query}/",
                            "publishers": epub_data.get("publishers", []),
                        }
                    )
            except Exception:
                pass
        return results
