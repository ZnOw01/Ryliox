"""Download orchestration plugin."""

from __future__ import annotations

import contextlib
import inspect
import secrets
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse

from core.contracts import ChapterInfo, DownloadCancelledError
from core.http_client import host_is_allowed
from plugins.base import Plugin


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
    async def download_image(self, url: str, save_path: Path) -> Path | None: ...

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

    def create_staging_dir(self, output_dir: Path, job_id: str) -> Path: ...

    def publish_staged_dir(self, staged_book_dir: Path, output_dir: Path, book_id: str) -> Path: ...

    def cleanup_staging(self, staging_dir: Path) -> None: ...


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

    def cleanup_build_artifacts(self, output_dir: Path) -> None: ...


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
    def parse_formats(cls, format_input: str | list[str] | None) -> list[str]:
        """Parse format specification into canonical format names."""
        if format_input is None:
            return ["epub"]

        if isinstance(format_input, list):
            raw_formats = [fmt.strip().lower() for fmt in format_input]
        else:
            raw_formats = [f.strip().lower() for f in format_input.split(",") if f.strip()]

        if not raw_formats:
            raise ValueError("At least one download format is required")

        unknown = [
            fmt
            for fmt in raw_formats
            if fmt != "all" and cls.FORMAT_ALIASES.get(fmt, fmt) not in cls.SUPPORTED_FORMATS
        ]
        if unknown:
            raise ValueError(f"Unknown download format(s): {', '.join(sorted(set(unknown)))}")

        if "all" in raw_formats:
            return ["epub", "pdf"]

        formats: list[str] = []
        seen: set[str] = set()

        for fmt in raw_formats:
            canonical = cls.FORMAT_ALIASES.get(fmt, fmt)
            if canonical in seen:
                continue
            formats.append(canonical)
            seen.add(canonical)

        return formats if formats else ["epub"]

    @classmethod
    def get_format_help(cls) -> dict[str, str]:
        """Return format descriptions for CLI help or UI display."""
        return {
            "epub": "Standard EPUB format (default)",
            "pdf": "Single PDF with the whole book or the selected chapters",
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
        return url if host_is_allowed(host) else ""

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
        job_id: str | None = None,
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

        def ensure_not_cancelled() -> None:
            """Abort the pipeline with a typed error once cancel was requested."""
            if check_cancel():
                raise DownloadCancelledError("Download cancelled by user")

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

        toc = await chapters_plugin.fetch_toc(book_id)
        reorder = getattr(chapters_plugin, "reorder_by_toc", None)
        if callable(reorder):
            all_chapters = reorder(all_chapters, toc)

        if selected_chapters is not None:
            selected_set = set(selected_chapters)
            if not selected_set.issubset(range(len(all_chapters))):
                raise ValueError("Selected chapters did not match the available chapter set")
            chapters = [ch for i, ch in enumerate(all_chapters) if i in selected_set]
        else:
            chapters = all_chapters

        # Build everything inside a managed staging area so the output dir only
        # ever observes complete books. Output plugins without staging support
        # (legacy) fall back to writing directly into the output dir.
        use_staging = all(
            hasattr(output_plugin, name)
            for name in ("create_staging_dir", "publish_staged_dir", "cleanup_staging")
        )
        staging_dir: Path | None
        if use_staging:
            job_token = job_id or secrets.token_hex(8)
            staging_dir = output_plugin.create_staging_dir(output_dir, job_token)
        else:
            staging_dir = None

        book_dir: Path | None = None
        try:
            book_dir = output_plugin.create_book_dir(
                output_dir=staging_dir if staging_dir is not None else output_dir,
                book_id=book_id,
                title=book_info.get("title", ""),
                authors=book_info.get("authors"),
            )
            oebps = output_plugin.get_oebps_dir(book_dir)

            # Phase 3: Download cover
            cover_image_name: str | None = None
            if not skip_images:
                report("downloading_cover", 12)
                cover_url = book_info.get("cover_url")
                if cover_url:
                    images_dir = output_plugin.get_images_dir(book_dir)
                    images_dir.mkdir(parents=True, exist_ok=True)
                    cover_path = await assets_plugin.download_image(cover_url, images_dir / "cover")
                    if cover_path:
                        cover_image_name = cover_path.relative_to(images_dir).as_posix()

            # Phase 4: Process chapters
            all_css_urls: set[str] = set()
            all_image_urls: set[str] = set()
            chapters_count = 0
            total_chapters = len(chapters)
            chapter_times: list[float] = []
            chapter_start_time = time.time()

            for i, ch in enumerate(chapters):
                ensure_not_cancelled()

                chapter_pct = 15 + int((i / total_chapters) * 65) if total_chapters > 0 else 15
                eta_seconds = None
                if chapter_times:
                    avg_time = sum(chapter_times[-5:]) / len(chapter_times[-5:])
                    eta_seconds = int(avg_time * (total_chapters - i))

                report(
                    "processing_chapters",
                    chapter_pct,
                    eta_seconds=eta_seconds,
                    current_chapter=i + 1,
                    total_chapters=total_chapters,
                    chapter_title=ch.get("title", ""),
                )

                filename = ch["filename"].replace(".html", ".xhtml")
                file_path = (oebps / filename).resolve()
                try:
                    file_path.relative_to(oebps.resolve())
                except ValueError as exc:
                    raise ValueError(
                        f"Chapter filename escapes output directory: {filename}"
                    ) from exc
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

                css_refs = [
                    f"{path_prefix}Styles/Style{j:02d}.css" for j in range(len(all_css_urls))
                ]
                xhtml = html_processor.wrap_xhtml(processed, css_refs, ch["title"])

                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(xhtml, encoding="utf-8")

                chapters_count += 1

                chapter_times.append(time.time() - chapter_start_time)
                chapter_start_time = time.time()

            # Phase 5: Download assets
            report("downloading_assets", 80, eta_seconds=None)
            ensure_not_cancelled()

            import config

            image_list = []
            for img_url in all_image_urls:
                if img_url.startswith("/"):
                    img_url = f"{config.BASE_URL.rstrip('/')}{img_url}"
                image_list.append(img_url)

            css_list = list(all_css_urls)
            total_assets = len(css_list) + len(image_list)

            if total_assets > config.SETTINGS.http.max_assets_per_book:
                raise ValueError(
                    f"Book references {total_assets} assets; configured limit is "
                    f"{config.SETTINGS.http.max_assets_per_book}"
                )

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

            ensure_not_cancelled()

            # Phase 6: Generate output formats
            epub_path: Path | None = None
            pdf_paths: Path | list[Path] | None = None

            if "epub" in formats:
                ensure_not_cancelled()
                report("generating_epub", 90)
                epub_plugin = cast("EpubPluginProtocol", self._plugin("epub"))
                epub_path = await self._resolve_result(
                    epub_plugin.generate(
                        book_info=book_info,
                        chapters=chapters,
                        toc=toc,
                        output_dir=book_dir,
                        css_files=css_list,
                        cover_image=cover_image_name or "cover.jpg",
                    )
                )
                ensure_not_cancelled()

            if any(f in formats for f in ("pdf", "all", "pdf-chapters")):
                pdf_plugin = cast("PdfPluginProtocol", self._plugin("pdf"))
                ensure_not_cancelled()

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
                else:
                    report("generating_pdf", 95)
                    pdf_paths = await self._resolve_result(
                        pdf_plugin.generate(
                            book_info=book_info,
                            chapters=chapters,
                            toc=toc,
                            output_dir=book_dir,
                            css_files=css_list,
                            cover_image=cover_image_name or "cover.jpg",
                        )
                    )
                ensure_not_cancelled()

            if "epub" in formats:
                cleanup = getattr(epub_plugin, "cleanup_build_artifacts", None)
                if callable(cleanup):
                    cleanup(book_dir)

            # Validate every generated output while the build is still private.
            # A plugin returning a path outside the staged book must fail before
            # publication, otherwise the job could expose a complete directory
            # and then be marked failed while rewriting result paths.
            epub_relative = epub_path.relative_to(book_dir) if epub_path is not None else None
            pdf_relatives: Path | list[Path] | None
            if isinstance(pdf_paths, list):
                pdf_relatives = [path.relative_to(book_dir) for path in pdf_paths]
            elif pdf_paths is not None:
                pdf_relatives = pdf_paths.relative_to(book_dir)
            else:
                pdf_relatives = None

            # The queue repository owns the terminal "completed" transition.
            # Keep the final progress update non-terminal, then perform one last
            # cancellation check before publication becomes externally visible.
            report("finalizing", 99)
            ensure_not_cancelled()

            if staging_dir is not None:
                published_dir = output_plugin.publish_staged_dir(book_dir, output_dir, book_id)
                # Publication is the commit point. Failure to remove the now
                # private staging container must not turn a complete output
                # into a failed job.
                with contextlib.suppress(Exception):
                    output_plugin.cleanup_staging(staging_dir)
            else:
                published_dir = book_dir

            result = DownloadResult(
                book_id=book_id,
                title=book_info.get("title", ""),
                output_dir=published_dir,
                chapters_count=chapters_count,
            )
            if epub_relative is not None:
                result.files["epub"] = str(published_dir / epub_relative)
            if pdf_relatives is not None:
                if isinstance(pdf_relatives, list):
                    result.files["pdf"] = [
                        str(published_dir / relative_path) for relative_path in pdf_relatives
                    ]
                else:
                    result.files["pdf"] = str(published_dir / pdf_relatives)

            return result
        except Exception as exc:
            if staging_dir is not None:
                with contextlib.suppress(Exception):
                    output_plugin.cleanup_staging(staging_dir)
            elif book_dir is not None and isinstance(exc, DownloadCancelledError):
                self._cleanup_on_cancel(book_dir)
            raise

    def _cleanup_on_cancel(self, book_dir: Path) -> None:
        """Remove build-only artifacts without deleting completed outputs."""
        for artifact_name in ("mimetype", "META-INF", "OEBPS"):
            artifact = book_dir / artifact_name
            if artifact.is_file():
                artifact.unlink()
            elif artifact.is_dir():
                shutil.rmtree(artifact)
