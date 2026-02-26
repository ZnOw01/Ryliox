import re
from urllib.parse import quote

import config
from core.types import ChapterInfo

from .base import Plugin

_COVER_WORD_RE = re.compile(r"\bcover\b", re.IGNORECASE)


class ChaptersPlugin(Plugin):
    """Plugin for fetching book chapters and their content."""

    async def fetch_list(self, book_id: str) -> list[ChapterInfo]:
        """Fetch list of chapters for a book."""
        encoded_book_id = quote(str(book_id).strip(), safe="")
        url = f"{config.API_V2}/epub-chapters/?epub_identifier=urn:orm:book:{encoded_book_id}"
        chapters: list[ChapterInfo] = []
        seen_urls: set[str] = set()

        while url and url not in seen_urls:
            seen_urls.add(url)
            data = await self.http.get_json(url)
            results = data.get("results", [])

            if not isinstance(results, list):
                results = []

            for ch in results:
                chapters.append(
                    ChapterInfo(
                        ourn=ch.get("ourn", ""),
                        title=ch.get("title", ""),
                        filename=self._extract_filename(ch.get("reference_id", "")),
                        content_url=ch.get("content_url", ""),
                        images=self._extract_related_urls(
                            ch.get("related_assets", {}).get("images", [])
                        ),
                        stylesheets=self._extract_related_urls(
                            ch.get("related_assets", {}).get("stylesheets", [])
                        ),
                        virtual_pages=ch.get("virtual_pages"),
                        minutes_required=ch.get("minutes_required"),
                    )
                )
            url = data.get("next")

        return self._reorder_cover_first(chapters)

    async def fetch_toc(self, book_id: str) -> list[dict]:
        encoded_book_id = quote(str(book_id).strip(), safe="")
        url = f"{config.API_V2}/epubs/urn:orm:book:{encoded_book_id}/table-of-contents/"
        return await self.http.get_json(url)

    async def fetch_content(self, content_url: str) -> str:
        return await self.http.get_text(content_url)

    def _extract_filename(self, reference_id: str) -> str:
        if "-/" in reference_id:
            return reference_id.split("-/", 1)[-1]
        return reference_id

    def _reorder_cover_first(self, chapters: list[ChapterInfo]) -> list[ChapterInfo]:
        """Reorder chapters to ensure cover comes first."""
        cover_chapters: list[ChapterInfo] = []
        other_chapters: list[ChapterInfo] = []

        for ch in chapters:
            filename_lower = ch["filename"].lower()
            title = ch["title"]

            is_cover = "cover" in filename_lower or bool(_COVER_WORD_RE.search(title))

            if is_cover:
                cover_chapters.append(ch)
            else:
                other_chapters.append(ch)

        return cover_chapters + other_chapters

    def _extract_related_urls(self, payload) -> list[str]:
        """Deeply extract media URLs from a dynamic JSON payload."""
        urls: list[str] = []
        seen: set[str] = set()

        url_keys = frozenset({"url", "href", "src", "asset_url", "content_url"})

        def push(value):
            candidate = str(value or "").strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                urls.append(candidate)

        def visit(node):
            if isinstance(node, str):
                push(node)
                return
            if isinstance(node, list):
                for item in node:
                    visit(item)
                return
            if isinstance(node, dict):
                for key in url_keys:
                    if key in node and isinstance(node[key], str):
                        push(node[key])

                for value in node.values():
                    if isinstance(value, (list, dict)):
                        visit(value)

        visit(payload)
        return urls
