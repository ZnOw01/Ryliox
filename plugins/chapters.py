import ipaddress
import logging
import re
from urllib.parse import quote, urljoin, urlparse

import config
from core.cache import get_chapter_list_cache, invalidate_book_cache
from core.types import ChapterInfo

from .base import Plugin

logger = logging.getLogger(__name__)
_COVER_WORD_RE = re.compile(r"\bcover\b", re.IGNORECASE)


class ChaptersPlugin(Plugin):
    """Plugin for fetching book chapters and their content."""

    def __init__(self) -> None:
        super().__init__()
        self._chapter_cache = get_chapter_list_cache()

    async def fetch_list(self, book_id: str) -> list[ChapterInfo]:
        """Fetch list of chapters for a book with caching."""
        cache_key = f"chapters:{book_id}"

        # Try cache first
        cached = await self._chapter_cache.get(cache_key)
        if cached is not None:
            return cached

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
                content_url = self._sanitize_remote_url(ch.get("content_url", ""))
                if not content_url:
                    logger.warning(
                        "Skipping chapter with blocked content_url: %r",
                        ch.get("content_url"),
                    )
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
            url = data.get("next")

        result = self._reorder_cover_first(chapters)

        # Cache the result
        await self._chapter_cache.set(cache_key, result)
        return result

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
            normalized = self._sanitize_remote_url(candidate, base_url=base_url)
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
        value = str(raw_url or "").strip()
        if not value or value.startswith("data:"):
            return ""

        if value.startswith("//"):
            value = f"https:{value}"
        elif not value.startswith(("http://", "https://")):
            value = urljoin(base_url or config.BASE_URL, value)

        try:
            parsed = urlparse(value)
        except ValueError:
            return ""

        if parsed.scheme not in {"http", "https"}:
            return ""

        host = (parsed.hostname or "").lower()
        if not host:
            return ""

        if host == "localhost" or host.endswith(".local"):
            return ""

        # S7: Validar que el host pertenezca al dominio permitido (whitelist)
        base_parsed = urlparse(config.BASE_URL)
        allowed_hostname = (base_parsed.hostname or "").lower()
        if allowed_hostname and not (
            host == allowed_hostname or host.endswith(f".{allowed_hostname}")
        ):
            logger.warning(
                "URL host %r no está en la whitelist de dominios permitidos", host
            )
            return ""

        try:
            ip = ipaddress.ip_address(host)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
            ):
                return ""
        except ValueError:
            pass

        return value
