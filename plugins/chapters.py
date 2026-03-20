import logging
import re
from urllib.parse import quote

import config
from core.types import ChapterInfo
from core.url_utils import sanitize_remote_url

from .base import Plugin

logger = logging.getLogger(__name__)
_COVER_WORD_RE = re.compile(r"\bcover\b", re.IGNORECASE)
_MAX_CHAPTER_PAGES = 100


class ChaptersPlugin(Plugin):
    """Plugin for fetching book chapters and their content."""

    async def fetch_list(self, book_id: str) -> list[ChapterInfo]:
        """Fetch list of chapters for a book."""
        encoded_book_id = quote(str(book_id).strip(), safe="")
        url = f"{config.API_V2}/epub-chapters/?epub_identifier=urn:orm:book:{encoded_book_id}"
        chapters: list[ChapterInfo] = []
        seen_urls: set[str] = set()
        page_count = 0

        while url and url not in seen_urls and page_count < _MAX_CHAPTER_PAGES:
            page_count += 1
            seen_urls.add(url)
            data = await self.http.get_json(url)
            results = data.get("results", [])

            if not isinstance(results, list):
                results = []

            for ch in results:
                content_url = sanitize_remote_url(ch.get("content_url", ""))
                if not content_url:
                    logger.warning("Skipping chapter with blocked content_url: %r", ch.get("content_url"))
                    continue

                chapters.append(
                    ChapterInfo(
                        ourn=ch.get("ourn", ""),
                        title=ch.get("title", ""),
                        filename=self._extract_filename(ch.get("reference_id", "")),
                        content_url=content_url,
                        images=self._extract_related_urls(
                            ch.get("related_assets", {}).get("images", []),
                            base_url=content_url,
                        ),
                        stylesheets=self._extract_related_urls(
                            ch.get("related_assets", {}).get("stylesheets", []),
                            base_url=content_url,
                        ),
                        virtual_pages=ch.get("virtual_pages"),
                        minutes_required=ch.get("minutes_required"),
                    )
                )
            next_url = sanitize_remote_url(data.get("next", ""), base_url=url)
            url = next_url or ""

        if page_count >= _MAX_CHAPTER_PAGES:
            logger.warning("Stopped chapter pagination for %s after %s pages", book_id, _MAX_CHAPTER_PAGES)

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

    def _extract_related_urls(self, payload, *, base_url: str = "") -> list[str]:
        """Deeply extract media URLs from a dynamic JSON payload."""
        urls: list[str] = []
        seen: set[str] = set()

        url_keys = frozenset({"url", "href", "src", "asset_url", "content_url"})

        def push(value):
            candidate = str(value or "").strip()
            normalized = sanitize_remote_url(candidate, base_url=base_url)
            if normalized and normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)

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

    def _sanitize_remote_url(self, raw_url: str, *, base_url: str = "") -> str:
        return sanitize_remote_url(raw_url, base_url=base_url)
