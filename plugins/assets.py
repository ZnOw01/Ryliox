"""Assets plugin: download images, CSS, and cover art for an EPUB."""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .base import Plugin

# Matches url(...) references inside stylesheets; shared with pdf.py.
CSS_URL_RE = re.compile(r'url\(["\']?([^)"\']+)["\']?\)')

_IMAGE_MAGIC: dict[bytes, str] = {
    b"\x89PNG": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",
}


def _detect_image_ext(data: bytes) -> str | None:
    for magic, ext in _IMAGE_MAGIC.items():
        if data.startswith(magic):
            if ext == ".webp" and len(data) > 8 and data[8:12] == b"WEBP":
                return ext
            return ext
    if data.startswith((b"<svg", b"<?xml", b"<html")):
        return ".svg"
    return None


class AssetsPlugin(Plugin):
    async def download_image(self, url: str, save_path: Path) -> Path | None:
        if save_path.exists():
            return save_path

        save_path.parent.mkdir(parents=True, exist_ok=True)
        content = await self.http.get_bytes(url)
        if not content:
            return None
        actual_ext = _detect_image_ext(content)
        if actual_ext and save_path.suffix.lower() != actual_ext:
            save_path = save_path.with_suffix(actual_ext)
        save_path.write_bytes(content)
        return save_path

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
            downloaded_path = await self.download_image(url, save_path)
            downloaded[url] = downloaded_path or save_path
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

    async def download_css_assets(self, css_urls: list[str], oebps: Path) -> None:
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
            for match in CSS_URL_RE.finditer(css_text):
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
