"""Assets downloader plugin."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

from .base import Plugin

ASSET_DOWNLOAD_CONCURRENCY_LIMIT = 8
logger = logging.getLogger(__name__)


class AssetsPlugin(Plugin):
    """Plugin para descargar y guardar archivos estáticos (imágenes, CSS)."""

    async def download_image(self, url: str, save_path: Path) -> bool:
        """Download image bytes and save to disk."""
        if await asyncio.to_thread(save_path.exists):
            return True

        try:
            await asyncio.to_thread(save_path.parent.mkdir, parents=True, exist_ok=True)
        except FileExistsError:
            pass

        content = await self.http.get_bytes(url)
        await asyncio.to_thread(save_path.write_bytes, content)
        return True

    async def download_css(self, url: str, save_path: Path) -> bool:
        """Download CSS text and save to disk."""
        if await asyncio.to_thread(save_path.exists):
            return True

        try:
            await asyncio.to_thread(save_path.parent.mkdir, parents=True, exist_ok=True)
        except FileExistsError:
            pass

        content = await self.http.get_text(url)
        await asyncio.to_thread(
            save_path.write_bytes,
            str(content).encode("utf-8", errors="replace"),
        )
        return True

    async def _download_all(
        self,
        urls: list[str],
        build_path: Callable[[int, str], Path],
        download_fn: Callable[[str, Path], Awaitable[bool]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]:
        """Download URLs concurrently and return the saved paths."""
        downloaded: dict[str, Path] = {}
        total = len(urls)
        if total == 0:
            return downloaded

        semaphore = asyncio.Semaphore(ASSET_DOWNLOAD_CONCURRENCY_LIMIT)
        progress_lock = asyncio.Lock()
        completed = 0

        async def worker(index: int, url: str) -> tuple[str, Path] | None:
            nonlocal completed

            save_path = build_path(index, url)

            try:
                async with semaphore:
                    await download_fn(url, save_path)
                success = True
            except Exception as e:
                logger.warning("Error downloading asset [%s]: %s", url, e)
                success = False
            finally:
                async with progress_lock:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

            if success:
                return url, save_path
            return None

        results = await asyncio.gather(*(worker(i, url) for i, url in enumerate(urls)))

        for result in results:
            if result is not None:
                url, save_path = result
                downloaded[url] = save_path

        return downloaded

    async def download_all_images(
        self,
        urls: list[str],
        output_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]:
        """Download all image assets."""

        def build_path(_: int, url: str) -> Path:
            parsed_url = urlparse(url)
            filename = parsed_url.path.split("/")[-1]
            if not filename:
                filename = "image_asset.bin"
            return output_dir / "Images" / filename

        return await self._download_all(
            urls=urls,
            build_path=build_path,
            download_fn=self.download_image,
            progress_callback=progress_callback,
        )

    async def download_all_css(
        self,
        urls: list[str],
        output_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]:
        """Download all CSS assets."""

        def build_path(index: int, _url: str) -> Path:
            return output_dir / "Styles" / f"Style{index:02d}.css"

        return await self._download_all(
            urls=urls,
            build_path=build_path,
            download_fn=self.download_css,
            progress_callback=progress_callback,
        )

    def get_cover_url(self, book_id: str) -> str:
        """Return the predictable cover URL for a book."""
        return f"https://learning.oreilly.com/library/cover/{book_id}/"
