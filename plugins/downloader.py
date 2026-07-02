"""Download orchestration plugin."""

from __future__ import annotations

import inspect
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse

from core.contracts import ChapterInfo
from plugins.base import Plugin

_ALLOWED_DOWNLOAD_HOSTS: tuple[str, ...] = (
    "oreilly.com",
    "oreillystatic.com",
    "oreil.ly",
)


@dataclass
class DownloadProgress:
    """Progress state for download operations."""

    status: str
    percentage: int = 0
    message: str = ""
    eta_seconds: int | None = None
    current_chapter: int = 0
    total_chapters: int = 0
    chapter_title: str = ""
    book_id: str = ""


@dataclass
class DownloadResult:
    """Result of a completed download."""

    book_id: str
    title: str
    output_dir: Path
    files: dict[str, str | list[str]] = field(default_factory=dict)
    chapters_count: int = 0


class BookPluginProtocol(Protocol):
    async def fetch(self, book_id: str) -> dict[str, Any]: ...


class ChaptersPluginProtocol(Protocol):
    async def fetch_list(self, book_id: str) -> list[ChapterInfo]: ...

    async def fetch_toc(self, book_id: str) -> list[dict[str, Any]]: ...

    def reorder_by_toc(
        self, chapters: list[ChapterInfo], toc: list[dict[str, Any]]
    ) -> list[ChapterInfo]: ...

    async def fetch_content(self, content_url: str) -> str: ...


class AssetsPluginProtocol(Protocol):
    async def download_image(self, url: str, save_path: Path) -> bool: ...

    async def download_all_css(
        self,
        urls: list[str],
        output_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]: ...

    async def download_css_assets(self, css_urls: list[str], oebps: Path) -> None: ...

    async def download_all_images(
        self,
        urls: list[str],
        output_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Path]: ...


class HtmlProcessorProtocol(Protocol):
    def process(
        self, html: str, book_id: str, skip_images: bool = False, path_prefix: str = ""
    ) -> tuple[str, list[str]]: ...

    def wrap_xhtml(self, content: str, css_files: list[str], title: str = "") -> str: ...

    def inline_css_content_images(self, oebps: Path) -> None: ...


class OutputPluginProtocol(Protocol):
    def create_book_dir(
        self,
        output_dir: Path,
        book_id: str,
        title: str,
        authors: list[str] | None = None,
    ) -> Path: ...

    def get_oebps_dir(self, book_dir: Path) -> Path: ...

    def get_images_dir(self, book_dir: Path) -> Path: ...


class EpubPluginProtocol(Protocol):
    def generate(
        self,
        book_info: dict[str, Any],
        chapters: list[ChapterInfo],
        toc: list[dict[str, Any]],
        output_dir: Path,
        css_files: list[str],
        cover_image: str | None = None,
    ) -> Path: ...


class PdfPluginProtocol(Protocol):
    def generate(
        self,
        book_info: dict[str, Any],
        chapters: list[ChapterInfo],
        toc: list[dict[str, Any]],
        output_dir: Path,
        css_files: list[str],
        cover_image: str | None = None,
    ) -> Path: ...

    def generate_chapters(
        self,
        book_info: dict[str, Any],
        chapters: list[ChapterInfo],
        output_dir: Path,
        css_files: list[str],
    ) -> list[Path]: ...


class DownloaderPlugin(Plugin):
    """Orchestrates the complete book download workflow."""

    # Public formats exposed to the UI. ``pdf-chapters`` is hidden from the
    # main list but still listed in ``descriptions`` so power users can
    # request it through the API.
    PUBLIC_FORMATS = ("epub", "pdf")
    INTERNAL_FORMATS = ("pdf-chapters",)
    SUPPORTED_FORMATS = frozenset(PUBLIC_FORMATS + INTERNAL_FORMATS)

    # Aliases for user convenience (e.g., CLI shorthand)
    FORMAT_ALIASES: dict[str, str] = {}

    # Formats that only support entire book (no chapter selection)
    BOOK_ONLY_FORMATS = frozenset(["epub"])

    def __init__(
        self,
        *,
        book_plugin: object | None = None,
        chapters_plugin: object | None = None,
        assets_plugin: object | None = None,
        html_processor_plugin: object | None = None,
        output_plugin: object | None = None,
        epub_plugin: object | None = None,
        pdf_plugin: object | None = None,
    ) -> None:
        self._injected = {
            "book": book_plugin,
            "chapters": chapters_plugin,
            "assets": assets_plugin,
            "html_processor": html_processor_plugin,
            "output": output_plugin,
            "epub": epub_plugin,
            "pdf": pdf_plugin,
        }

    def _plugin(self, name: str) -> object:
        injected = self._injected.get(name)
        if injected is not None:
            return injected
        kernel = getattr(self, "kernel", None)
        if kernel is None:
            raise RuntimeError(
                f"DownloaderPlugin has no '{name}' plugin injected and no kernel to resolve it"
            )
        getter = getattr(kernel, "__getitem__", None)
        if not callable(getter):
            raise RuntimeError(f"Kernel does not support plugin lookup for '{name}'")
        return getter(name)

    @classmethod
    def parse_formats(cls, format_input: str | list[str]) -> list[str]:
        """Parse format specification into canonical format names."""
        if isinstance(format_input, list):
            raw_formats = format_input
        else:
            if format_input == "all":
                return ["epub", "pdf"]
            raw_formats = [f.strip().lower() for f in format_input.split(",") if f.strip()]

        formats: list[str] = []
        seen: set[str] = set()

        for fmt in raw_formats:
            canonical = cls.FORMAT_ALIASES.get(fmt, fmt)
            if canonical not in cls.SUPPORTED_FORMATS or canonical in seen:
                continue
            formats.append(canonical)
            seen.add(canonical)

        return formats if formats else ["epub"]

    @classmethod
    def get_format_help(cls) -> dict[str, str]:
        """Return format descriptions for CLI help or UI display."""
        return {
            "epub": "Standard EPUB format (default)",
            "pdf": "Un solo PDF con el libro completo o con los capitulos seleccionados.",
            "pdf-chapters": "Separate PDF per chapter",
        }

    @classmethod
    def supports_chapter_selection(cls, fmt: str) -> bool:
        """Check if a format supports chapter selection."""
        canonical = cls.FORMAT_ALIASES.get(fmt, fmt)
        return canonical not in cls.BOOK_ONLY_FORMATS

    @classmethod
    def get_formats_info(cls) -> dict[str, Any]:
        """Return complete format information for discovery endpoints."""
        return {
            "formats": list(cls.PUBLIC_FORMATS),
            "aliases": cls.FORMAT_ALIASES,
            "book_only": sorted(cls.BOOK_ONLY_FORMATS),
            "descriptions": cls.get_format_help(),
        }

    @staticmethod
    def _normalize_asset_url(base: str, url: str) -> str:
        """Return the URL if its host is allowed, else ``""``.

        ``base`` is accepted for symmetry with the CSS asset-rewriter and
        ignored — only the URL's own host is consulted.
        """
        if not url:
            return ""
        host = (urlparse(url).hostname or "").lower()
        for allowed in _ALLOWED_DOWNLOAD_HOSTS:
            if host == allowed or host.endswith("." + allowed):
                return url
        return ""

    @staticmethod
    async def _resolve_result(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def download(
        self,
        book_id: str,
        output_dir: Path,
        formats: list[str] | None = None,
        selected_chapters: list[int] | None = None,
        skip_images: bool = False,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> DownloadResult:
        """Orchestrate full download pipeline for a book."""
        if formats is None:
            formats = ["epub"]

        def report(
            status: str,
            percentage: int = 0,
            message: str = "",
            eta_seconds: int | None = None,
            current_chapter: int = 0,
            total_chapters: int = 0,
            chapter_title: str = "",
        ) -> None:
            if progress_callback:
                progress_callback(
                    DownloadProgress(
                        status=status,
                        percentage=percentage,
                        message=message,
                        eta_seconds=eta_seconds,
                        current_chapter=current_chapter,
                        total_chapters=total_chapters,
                        chapter_title=chapter_title,
                        book_id=book_id,
                    )
                )

        def check_cancel() -> bool:
            return bool(cancel_check and cancel_check())

        # Reject chapter selection on book-only formats BEFORE doing any work.
        for fmt in formats:
            if not self.supports_chapter_selection(fmt) and selected_chapters:
                raise ValueError(f"Chapter selection not supported for: {fmt}")

        book_plugin = cast("BookPluginProtocol", self._plugin("book"))
        chapters_plugin = cast("ChaptersPluginProtocol", self._plugin("chapters"))
        assets_plugin = cast("AssetsPluginProtocol", self._plugin("assets"))
        html_processor = cast("HtmlProcessorProtocol", self._plugin("html_processor"))
        output_plugin = cast("OutputPluginProtocol", self._plugin("output"))

        # Phase 1: Validate session and fetch metadata
        report("starting", 0)
        http_client = self.http
        if http_client is not None:
            jwt_status = http_client.get_jwt_status()
            if (
                jwt_status is not None
                and not jwt_status["valid"]
                and not http_client.has_refresh_cookie()
            ):
                raise RuntimeError(
                    "Session token expired. Please copy fresh cookies from your browser and POST them to /api/cookies."
                )

        report("fetching_metadata", 5)
        book_info = await book_plugin.fetch(book_id)

        # Phase 2: Fetch chapters list
        report("fetching_chapters", 10)
        all_chapters = await chapters_plugin.fetch_list(book_id)

        # Filter chapters if selection provided; verify the indexes match.
        # Must come AFTER the fetch so we know the real chapter count, but we
        # do it before creating the output directory so a bad selection aborts
        # cleanly without leaving half-written files.
        if selected_chapters is not None:
            selected_set = set(selected_chapters)
            if not selected_set.issubset(range(len(all_chapters))):
                raise ValueError("Selected chapters did not match the available chapter set")
            chapters = [ch for i, ch in enumerate(all_chapters) if i in selected_set]
        else:
            chapters = all_chapters

        toc = await chapters_plugin.fetch_toc(book_id)
        reorder = getattr(chapters_plugin, "reorder_by_toc", None)
        if callable(reorder):
            all_chapters = reorder(all_chapters, toc)
            if selected_chapters is not None:
                selected_set = set(selected_chapters)
                chapters = [ch for i, ch in enumerate(all_chapters) if i in selected_set]
            else:
                chapters = all_chapters

        # Create output directory
        book_dir = output_plugin.create_book_dir(
            output_dir=output_dir,
            book_id=book_id,
            title=book_info.get("title", ""),
            authors=book_info.get("authors"),
        )
        oebps = output_plugin.get_oebps_dir(book_dir)

        # Phase 3: Download cover
        if not skip_images:
            report("downloading_cover", 12)
            cover_url = book_info.get("cover_url")
            if cover_url:
                images_dir = output_plugin.get_images_dir(book_dir)
                images_dir.mkdir(parents=True, exist_ok=True)
                await assets_plugin.download_image(cover_url, images_dir / "cover.jpg")

        # Phase 4: Process chapters
        all_css_urls: set[str] = set()
        all_image_urls: set[str] = set()
        chapters_data: list[tuple[str, str, str]] = []
        total_chapters = len(chapters)
        chapter_times: list[float] = []
        chapter_start_time = time.time()

        for i, ch in enumerate(chapters):
            if check_cancel():
                self._cleanup_on_cancel(book_dir)
                raise Exception("Download cancelled by user")

            chapter_pct = 15 + int((i / total_chapters) * 65) if total_chapters > 0 else 15

            report(
                "processing_chapters",
                chapter_pct,
                current_chapter=i + 1,
                total_chapters=total_chapters,
                chapter_title=ch.get("title", ""),
            )

            filename = ch["filename"].replace(".html", ".xhtml")
            depth = filename.count("/")
            path_prefix = "../" * depth if depth > 0 else ""

            raw_html = await chapters_plugin.fetch_content(ch["content_url"])
            processed, images = html_processor.process(
                raw_html, book_id, skip_images=skip_images, path_prefix=path_prefix
            )

            all_css_urls.update(ch["stylesheets"])
            for img_url in ch["images"]:
                all_image_urls.add(img_url)
            for img_url in images:
                if img_url.startswith("http") or img_url.startswith("/"):
                    all_image_urls.add(img_url)

            css_refs = [f"{path_prefix}Styles/Style{j:02d}.css" for j in range(len(all_css_urls))]
            xhtml = html_processor.wrap_xhtml(processed, css_refs, ch["title"])

            file_path = oebps / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(xhtml, encoding="utf-8")

            chapters_data.append((ch["filename"], ch["title"], processed))

            chapter_time = time.time() - chapter_start_time
            chapter_times.append(chapter_time)
            chapter_start_time = time.time()

            if chapter_times:
                avg_time = sum(chapter_times[-5:]) / len(chapter_times[-5:])
                remaining = total_chapters - (i + 1)
                eta_seconds = int(avg_time * remaining)
                report(
                    "processing_chapters",
                    chapter_pct,
                    eta_seconds=eta_seconds,
                    current_chapter=i + 1,
                    total_chapters=total_chapters,
                    chapter_title=ch.get("title", ""),
                )

        # Phase 5: Download assets
        report("downloading_assets", 80, eta_seconds=None)

        image_list = []
        for img_url in all_image_urls:
            if img_url.startswith("/"):
                img_url = f"https://learning.oreilly.com{img_url}"
            image_list.append(img_url)

        css_list = list(all_css_urls)
        total_assets = len(css_list) + len(image_list)

        css_width = len(str(len(css_list)))

        def css_progress(completed: int, total: int) -> None:
            if total_assets > 0:
                pct = 80 + int((completed / total_assets) * 10)
                report(
                    "downloading_assets",
                    pct,
                    f"{pct:2d}% - Downloading CSS ({completed:>{css_width}}/{len(css_list)})",
                )

        await assets_plugin.download_all_css(css_list, oebps, progress_callback=css_progress)

        if not skip_images:
            await assets_plugin.download_css_assets(css_list, oebps)
            html_processor.inline_css_content_images(oebps)

        if not skip_images:
            img_width = len(str(len(image_list)))

            def image_progress(completed: int, total: int) -> None:
                if total_assets > 0:
                    pct = 80 + int(((len(css_list) + completed) / total_assets) * 10)
                    report(
                        "downloading_assets",
                        pct,
                        f"{pct:2d}% - Downloading images ({completed:>{img_width}}/{len(image_list)})",
                    )

            await assets_plugin.download_all_images(
                image_list, oebps, progress_callback=image_progress
            )

        # Phase 6: Generate output formats
        result = DownloadResult(
            book_id=book_id,
            title=book_info.get("title", ""),
            output_dir=book_dir,
            chapters_count=len(chapters_data),
        )

        if "epub" in formats:
            report("generating_epub", 90)
            epub_plugin = cast("EpubPluginProtocol", self._plugin("epub"))
            epub_path = await self._resolve_result(
                epub_plugin.generate(
                    book_info=book_info,
                    chapters=chapters,
                    toc=toc,
                    output_dir=book_dir,
                    css_files=css_list,
                    cover_image="cover.jpg",
                )
            )
            result.files["epub"] = str(epub_path)

        if any(f in formats for f in ("pdf", "all", "pdf-chapters")):
            pdf_plugin = cast("PdfPluginProtocol", self._plugin("pdf"))

            if "pdf-chapters" in formats:
                report("generating_pdf_chapters", 95)
                pdf_paths = await self._resolve_result(
                    pdf_plugin.generate_chapters(
                        book_info=book_info,
                        chapters=chapters,
                        output_dir=book_dir,
                        css_files=css_list,
                    )
                )
                result.files["pdf"] = [str(p) for p in pdf_paths]
            else:
                report("generating_pdf", 95)
                pdf_path = await self._resolve_result(
                    pdf_plugin.generate(
                        book_info=book_info,
                        chapters=chapters,
                        toc=toc,
                        output_dir=book_dir,
                        css_files=css_list,
                        cover_image="cover.jpg",
                    )
                )
                result.files["pdf"] = str(pdf_path)

        report("completed", 100)
        return result

    def _cleanup_on_cancel(self, book_dir: Path) -> None:
        """Clean up partially downloaded book on cancellation."""
        if book_dir.exists():
            shutil.rmtree(book_dir)
