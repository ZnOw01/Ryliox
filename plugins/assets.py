"""Assets plugin: download images, CSS, and cover art for an EPUB."""

from __future__ import annotations

import contextlib
import mimetypes
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .base import Plugin

_ALLOWED_ASSET_HOSTS: tuple[str, ...] = (
    "oreilly.com",
    "oreillystatic.com",
    "oreil.ly",
)

_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
}


class AssetsPlugin(Plugin):
    async def download_image(self, url: str, save_path: Path) -> bool:
        if save_path.exists():
            return True

        save_path.parent.mkdir(parents=True, exist_ok=True)
        content = await self.http.get_bytes(url)
        save_path.write_bytes(content)
        return True

    async def download_css(self, url: str, save_path: Path) -> bool:
        if save_path.exists():
            return True

        save_path.parent.mkdir(parents=True, exist_ok=True)
        content = await self.http.get_text(url)
        save_path.write_text(content, encoding="utf-8")
        return True

    async def download_all_images(
        self,
        urls: list[str],
        output_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]:
        downloaded: dict[str, Path] = {}
        total = len(urls)
        for i, url in enumerate(urls):
            filename = self._filename_from_url(url, default=f"image{i:03d}.bin")
            save_path = output_dir / "Images" / filename
            await self.download_image(url, save_path)
            downloaded[url] = save_path
            if progress_callback:
                progress_callback(i + 1, total)
        return downloaded

    async def download_all_css(
        self,
        urls: list[str],
        output_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]:
        downloaded: dict[str, Path] = {}
        total = len(urls)
        for i, url in enumerate(urls):
            save_path = output_dir / "Styles" / f"Style{i:02d}.css"
            await self.download_css(url, save_path)
            downloaded[url] = save_path
            if progress_callback:
                progress_callback(i + 1, total)
        return downloaded

    async def download_css_assets(self, css_urls: list[str], oebps: Path):
        """Download assets referenced by url() in CSS files."""
        styles_dir = oebps / "Styles"
        if not styles_dir.exists():
            return

        safe_styles_dir = styles_dir.resolve()
        for i, css_url in enumerate(css_urls):
            css_path = styles_dir / f"Style{i:02d}.css"
            if not css_path.exists():
                continue

            css_text = css_path.read_text(encoding="utf-8")
            for match in re.finditer(r'url\(["\']?([^)"\']+)["\']?\)', css_text):
                ref = match.group(1)
                ref_path = Path(ref)
                if (
                    ref.startswith(("data:", "http", "/", "\\"))
                    or ".." in ref_path.parts
                    or ref_path.is_absolute()
                ):
                    continue

                save_path = (safe_styles_dir / ref_path).resolve()
                try:
                    save_path.relative_to(safe_styles_dir)
                except ValueError:
                    continue
                if save_path.exists():
                    continue

                css_base = css_url.rsplit("/", 1)[0]
                asset_url = f"{css_base}/{ref}"
                with contextlib.suppress(Exception):
                    await self.download_image(asset_url, save_path)

    async def download_cover_image(self, cover_url: str, output_dir: Path) -> Path | None:
        """Download the cover image, picking an extension from the Content-Type.

        The cover URL on O'Reilly ends in ``.bin``/no extension; we cannot trust
        the URL suffix. We rely on the response's Content-Type header instead.
        """
        if not cover_url:
            return None
        response = await self.http.get(cover_url, allow_redirects=True)
        getattr(response, "raise_for_status", lambda: None)()

        content_type = (
            (response.headers or {}).get("content-type", "").split(";")[0].strip().lower()
        )
        ext = (
            _CONTENT_TYPE_TO_EXT.get(content_type)
            or mimetypes.guess_extension(content_type)
            or ".bin"
        )
        if ext == ".jpe":
            ext = ".jpg"

        output_dir.mkdir(parents=True, exist_ok=True)
        cover_path = output_dir / f"cover{ext}"
        cover_path.write_bytes(response.content)
        return cover_path

    def get_cover_url(self, book_id: str) -> str:
        return f"https://learning.oreilly.com/library/cover/{book_id}/"

    @staticmethod
    def _ensure_safe_asset_url(url: str) -> None:
        """Raise ``ValueError`` if ``url`` is not in an allowed host."""
        if not url or not url.startswith("http"):
            return
        host = (urlparse(url).hostname or "").lower()
        for allowed in _ALLOWED_ASSET_HOSTS:
            if host == allowed or host.endswith("." + allowed):
                return
        raise ValueError(f"Blocked asset host outside allowed hosts: {url}")

    @staticmethod
    def _filename_from_url(url: str, default: str = "asset.bin") -> str:
        """Return a stable, on-disk-safe filename for a URL.

        Strips query strings and fragments, takes the last path component, and
        falls back to ``default`` if the URL has no useful name.
        """
        parsed = urlparse(url)
        path = parsed.path or ""
        candidate = path.rsplit("/", 1)[-1] if path else ""
        if not candidate:
            return default
        # Disallow characters that break the filesystem; keep alnum + . _ -
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", candidate)
        return safe or default
