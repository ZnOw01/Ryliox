"""Download orchestration plugin."""

import asyncio
import shutil
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Awaitable, Callable
from urllib.parse import urljoin

from plugins.base import Plugin
from plugins.pdf import generate_pdf_chapters_in_subprocess, generate_pdf_in_subprocess


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


class DownloaderPlugin(Plugin):
    """Orchestrates the complete book download workflow."""

    SUPPORTED_FORMATS = frozenset(
        [
            "epub",
            "pdf",
            "pdf-chapters",
        ]
    )

    FORMAT_ALIASES: dict[str, str] = {}

    BOOK_ONLY_FORMATS = frozenset(["epub"])
    ASSET_DOWNLOAD_CONCURRENCY = 8

    def __init__(
        self,
        *,
        book_plugin=None,
        chapters_plugin=None,
        assets_plugin=None,
        html_processor_plugin=None,
        output_plugin=None,
        epub_plugin=None,
    ):
        self._book_plugin = book_plugin
        self._chapters_plugin = chapters_plugin
        self._assets_plugin = assets_plugin
        self._html_processor_plugin = html_processor_plugin
        self._output_plugin = output_plugin
        self._epub_plugin = epub_plugin

    @classmethod
    def parse_formats(cls, format_input: str | list[str]) -> list[str]:
        if format_input is None:
            return ["epub"]

        if isinstance(format_input, list):
            raw_formats = [
                str(f).strip().lower() for f in format_input if str(f).strip()
            ]
        else:
            normalized = str(format_input).strip().lower()
            if normalized == "all":
                return ["epub", "pdf"]
            raw_formats = [
                f.strip().lower() for f in normalized.split(",") if f.strip()
            ]

        formats = []
        seen = set()
        invalid = []

        for fmt in raw_formats:
            canonical = cls.FORMAT_ALIASES.get(fmt, fmt)

            if canonical not in cls.SUPPORTED_FORMATS:
                invalid.append(fmt)
                continue
            if canonical in seen:
                continue

            formats.append(canonical)
            seen.add(canonical)

        if invalid:
            supported = ", ".join(sorted(cls.SUPPORTED_FORMATS))
            invalid_str = ", ".join(invalid)
            raise ValueError(
                f"Unsupported format(s): {invalid_str}. Supported formats: {supported}"
            )

        return formats if formats else ["epub"]

    @classmethod
    def get_format_help(cls) -> dict[str, str]:
        return {
            "epub": "Standard EPUB format (default)",
            "pdf": "Single PDF file",
            "pdf-chapters": "Separate PDF per chapter",
        }

    @classmethod
    def supports_chapter_selection(cls, fmt: str) -> bool:
        canonical = cls.FORMAT_ALIASES.get(fmt, fmt)
        return canonical not in cls.BOOK_ONLY_FORMATS

    @classmethod
    def get_formats_info(cls) -> dict:
        return {
            "formats": sorted(cls.SUPPORTED_FORMATS),
            "aliases": cls.FORMAT_ALIASES,
            "book_only": sorted(cls.BOOK_ONLY_FORMATS),
            "descriptions": cls.get_format_help(),
        }

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
        if formats is None:
            formats = ["epub"]
        book_dir: Path | None = None

        def report(
            status: str,
            percentage: int = 0,
            message: str = "",
            eta_seconds: int | None = None,
            current_chapter: int = 0,
            total_chapters: int = 0,
            chapter_title: str = "",
        ):
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

        def check_cancel():
            return bool(cancel_check and cancel_check())

        async def abort_if_cancelled():
            if check_cancel():
                if book_dir is not None:
                    await asyncio.to_thread(self._cleanup_on_cancel, book_dir)
                raise asyncio.CancelledError("Download cancelled by user")

        book_plugin = self._book_plugin or self.kernel["book"]
        chapters_plugin = self._chapters_plugin or self.kernel["chapters"]
        assets_plugin = self._assets_plugin or self.kernel["assets"]
        html_processor = self._html_processor_plugin or self.kernel["html_processor"]
        output_plugin = self._output_plugin or self.kernel["output"]

        report("starting", 0)
        report("fetching_metadata", 5)
        book_info = await book_plugin.fetch(book_id)

        report("fetching_chapters", 10)
        all_chapters = await chapters_plugin.fetch_list(book_id)
        toc = await chapters_plugin.fetch_toc(book_id)
        await abort_if_cancelled()

        if selected_chapters is not None:
            selected_set = set(selected_chapters)
            chapters = [ch for i, ch in enumerate(all_chapters) if i in selected_set]
        else:
            chapters = all_chapters
        chapters = self._sanitize_chapters_for_output(chapters)

        book_dir = await asyncio.to_thread(
            output_plugin.create_book_dir,
            output_dir=output_dir,
            book_id=book_id,
            title=book_info.get("title", ""),
            authors=book_info.get("authors"),
        )
        oebps = output_plugin.get_oebps_dir(book_dir)

        if not skip_images:
            report("downloading_cover", 12)
            cover_url = book_info.get("cover_url")
            if cover_url:
                await abort_if_cancelled()
                images_dir = output_plugin.get_images_dir(book_dir)
                await asyncio.to_thread(images_dir.mkdir, parents=True, exist_ok=True)
                await assets_plugin.download_image(cover_url, images_dir / "cover.jpg")

        all_css_urls: list[str] = []
        seen_css_urls: set[str] = set()
        all_image_urls = set()
        total_chapters = len(chapters)

        chapter_times = deque(maxlen=5)
        chapter_start_time = time.time()

        for i, ch in enumerate(chapters):
            await abort_if_cancelled()

            chapter_pct = (
                15 + int((i / total_chapters) * 65) if total_chapters > 0 else 15
            )

            report(
                "processing_chapters",
                chapter_pct,
                current_chapter=i + 1,
                total_chapters=total_chapters,
                chapter_title=ch.get("title", ""),
            )

            chapter_href = str(ch["filename"])
            content_url = str(ch.get("content_url", "") or "")
            images_prefix = self._relative_asset_prefix(chapter_href, "Images")
            css_prefix = self._relative_asset_prefix(chapter_href, "Styles")

            raw_html = await chapters_plugin.fetch_content(content_url)
            await abort_if_cancelled()
            processed, images = await asyncio.to_thread(
                html_processor.process,
                raw_html,
                book_id,
                skip_images=skip_images,
                base_url=content_url,
                images_prefix=images_prefix,
            )
            await abort_if_cancelled()

            for css_url in ch.get("stylesheets") or []:
                normalized_css_url = self._normalize_asset_url(content_url, css_url)
                if normalized_css_url and normalized_css_url not in seen_css_urls:
                    seen_css_urls.add(normalized_css_url)
                    all_css_urls.append(normalized_css_url)

            for img_url in (ch.get("images") or []) + images:
                normalized_image_url = self._normalize_asset_url(content_url, img_url)
                if normalized_image_url:
                    all_image_urls.add(normalized_image_url)

            css_refs = [
                f"{css_prefix}/Style{j:02d}.css" for j in range(len(all_css_urls))
            ]
            xhtml = await asyncio.to_thread(
                html_processor.wrap_xhtml,
                processed,
                css_refs,
                ch["title"],
            )
            await abort_if_cancelled()

            file_path = oebps.joinpath(*PurePosixPath(chapter_href).parts)
            await asyncio.to_thread(self._write_chapter_xhtml, file_path, xhtml)
            await abort_if_cancelled()

            chapter_times.append(time.time() - chapter_start_time)
            chapter_start_time = time.time()

            if len(chapter_times) > 0:
                avg_time = sum(chapter_times) / len(chapter_times)
                eta_seconds = int(avg_time * (total_chapters - (i + 1)))
                report(
                    "processing_chapters",
                    chapter_pct,
                    eta_seconds=eta_seconds,
                    current_chapter=i + 1,
                    total_chapters=total_chapters,
                    chapter_title=ch.get("title", ""),
                )

        report("downloading_assets", 80, eta_seconds=None)

        image_tasks: list[tuple[str, str]] = []
        seen_image_filenames: set[str] = set()

        for img_url in all_image_urls:
            filename = html_processor.image_filename_from_url(img_url)
            if not filename:
                continue

            filename_key = filename.lower()
            if filename_key not in seen_image_filenames:
                seen_image_filenames.add(filename_key)
                image_tasks.append((img_url, filename))

        css_jobs = [
            (css_url, oebps / "Styles" / f"Style{index:02d}.css")
            for index, css_url in enumerate(all_css_urls)
        ]
        image_jobs = (
            [
                (img_url, oebps / "Images" / filename)
                for img_url, filename in image_tasks
            ]
            if not skip_images
            else []
        )

        total_assets = len(css_jobs) + len(image_jobs)

        if total_assets > 0:
            css_width = len(str(len(css_jobs) if css_jobs else 1))
            img_width = len(str(len(image_jobs) if image_jobs else 1))
            css_completed = 0
            image_completed = 0
            shared_asset_semaphore = asyncio.Semaphore(self.ASSET_DOWNLOAD_CONCURRENCY)

            def css_progress(completed: int, total: int):
                nonlocal css_completed
                if total_assets <= 0:
                    return
                css_completed = completed
                pct = 80 + int(((css_completed + image_completed) / total_assets) * 10)
                report(
                    "downloading_assets",
                    pct,
                    f"{pct:2d}% - Downloading CSS ({completed:>{css_width}}/{total})",
                )

            def image_progress(completed: int, total: int):
                nonlocal image_completed
                if total_assets <= 0:
                    return
                image_completed = completed
                pct = 80 + int(((css_completed + image_completed) / total_assets) * 10)
                report(
                    "downloading_assets",
                    pct,
                    f"{pct:2d}% - Downloading images ({completed:>{img_width}}/{total})",
                )

            asset_batches = []
            if css_jobs:
                asset_batches.append(
                    self._download_assets_concurrently(
                        jobs=css_jobs,
                        worker=lambda job: assets_plugin.download_css(job[0], job[1]),
                        cancel_check=check_cancel,
                        progress_callback=css_progress,
                        semaphore=shared_asset_semaphore,
                    )
                )
            if image_jobs:
                asset_batches.append(
                    self._download_assets_concurrently(
                        jobs=image_jobs,
                        worker=lambda job: assets_plugin.download_image(job[0], job[1]),
                        cancel_check=check_cancel,
                        progress_callback=image_progress,
                        semaphore=shared_asset_semaphore,
                    )
                )
            await asyncio.gather(*asset_batches)
            await abort_if_cancelled()

        result = DownloadResult(
            book_id=book_id,
            title=book_info.get("title", ""),
            output_dir=book_dir,
            chapters_count=total_chapters,
        )

        if "epub" in formats:
            report("generating_epub", 90)
            epub_plugin = self._epub_plugin or self.kernel["epub"]
            cover_image_name = self._resolve_cover_image_name(oebps)
            await abort_if_cancelled()
            epub_path = await asyncio.to_thread(
                epub_plugin.generate,
                book_info=book_info,
                chapters=chapters,
                toc=toc,
                output_dir=book_dir,
                css_files=all_css_urls,
                cover_image=cover_image_name,
            )
            await abort_if_cancelled()
            result.files["epub"] = str(epub_path)

        if "pdf" in formats or "pdf-chapters" in formats:
            cover_image_name = self._resolve_cover_image_name(oebps)
            loop = asyncio.get_running_loop()
            with ProcessPoolExecutor(max_workers=1) as process_pool:
                if "pdf-chapters" in formats:
                    report("generating_pdf_chapters", 95)
                    await abort_if_cancelled()
                    future = loop.run_in_executor(
                        process_pool,
                        generate_pdf_chapters_in_subprocess,
                        book_info,
                        chapters,
                        str(book_dir),
                        all_css_urls,
                    )
                    pdf_paths = await self._await_executor_future_with_cancel(
                        future=future,
                        cancel_check=check_cancel,
                        on_cancel=lambda: self._terminate_process_pool(process_pool),
                    )
                    await abort_if_cancelled()
                    result.files["pdf"] = pdf_paths
                else:
                    report("generating_pdf", 95)
                    await abort_if_cancelled()
                    future = loop.run_in_executor(
                        process_pool,
                        generate_pdf_in_subprocess,
                        book_info,
                        chapters,
                        toc,
                        str(book_dir),
                        all_css_urls,
                        cover_image_name,
                    )
                    pdf_path = await self._await_executor_future_with_cancel(
                        future=future,
                        cancel_check=check_cancel,
                        on_cancel=lambda: self._terminate_process_pool(process_pool),
                    )
                    await abort_if_cancelled()
                    result.files["pdf"] = pdf_path

        report("completed", 100)
        return result

    def _cleanup_on_cancel(self, book_dir: Path):
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)

    def _write_chapter_xhtml(self, file_path: Path, xhtml: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(str(xhtml).encode("utf-8", errors="replace"))

    async def _download_assets_concurrently(
        self,
        *,
        jobs: list[tuple[str, Path]],
        worker: Callable[[tuple[str, Path]], Awaitable[bool]],
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        if not jobs:
            return

        worker_semaphore = semaphore or asyncio.Semaphore(
            self.ASSET_DOWNLOAD_CONCURRENCY
        )
        completed = 0
        total = len(jobs)

        async def safe_worker(job: tuple[str, Path]):
            nonlocal completed
            if cancel_check and cancel_check():
                raise asyncio.CancelledError("Download cancelled")

            async with worker_semaphore:
                if cancel_check and cancel_check():
                    raise asyncio.CancelledError("Download cancelled")
                await worker(job)

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

        tasks = [asyncio.create_task(safe_worker(job)) for job in jobs]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise
        except Exception:
            for t in tasks:
                t.cancel()
            raise

    async def _await_executor_future_with_cancel(
        self,
        *,
        future: asyncio.Future,
        cancel_check: Callable[[], bool] | None = None,
        on_cancel: Callable[[], None] | None = None,
        poll_interval_seconds: float = 0.25,
    ):
        while True:
            try:
                return await asyncio.wait_for(
                    asyncio.shield(future), timeout=poll_interval_seconds
                )
            except asyncio.TimeoutError:
                if cancel_check and cancel_check():
                    if on_cancel:
                        try:
                            on_cancel()
                        except Exception:
                            pass
                    raise asyncio.CancelledError("Download cancelled by user")

    def _terminate_process_pool(self, process_pool: ProcessPoolExecutor) -> None:
        try:
            process_pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

        for process in getattr(process_pool, "_processes", {}).values():
            try:
                if process.is_alive():
                    process.terminate()
            except Exception:
                continue

    def _normalize_asset_url(self, base_url: str, asset_url: str) -> str:
        value = str(asset_url or "").strip()
        if not value or value.startswith("data:"):
            return ""
        if value.startswith("//"):
            return f"https:{value}"
        if value.startswith(("http://", "https://")):
            return value

        if base_url:
            return urljoin(base_url, value)

        return value

    def _resolve_cover_image_name(self, oebps: Path) -> str | None:
        images_dir = oebps / "Images"
        if not images_dir.exists():
            return None

        preferred = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp", "cover.gif")
        for name in preferred:
            if (images_dir / name).exists():
                return name

        files = sorted(
            [p for p in images_dir.iterdir() if p.is_file()],
            key=lambda p: p.name.lower(),
        )
        for file_path in files:
            if "cover" in file_path.stem.lower():
                return file_path.name
        if files:
            return files[0].name
        return None

    def _sanitize_chapters_for_output(self, chapters: list[dict]) -> list[dict]:
        sanitized: list[dict] = []
        for chapter in chapters:
            normalized_filename = self._normalize_chapter_output_href(
                chapter.get("filename")
            )
            if not normalized_filename:
                continue
            chapter_copy = dict(chapter)
            chapter_copy["filename"] = normalized_filename
            sanitized.append(chapter_copy)
        return sanitized

    def _normalize_chapter_output_href(self, reference: str | None) -> str:
        if reference is None:
            return ""

        href = str(reference).strip()
        if not href:
            return ""

        if "-/" in href:
            href = href.split("-/", 1)[1]

        href = href.split("?", 1)[0].split("#", 1)[0]
        href = href.replace("\\", "/").lstrip("/")

        if not href:
            return ""

        parts = [part for part in PurePosixPath(href).parts if part and part != "."]
        if not parts or ".." in parts:
            return ""

        normalized = str(PurePosixPath(*parts))
        lower_href = normalized.lower()

        if lower_href.endswith((".html", ".htm")):
            normalized = f"{normalized.rsplit('.', 1)[0]}.xhtml"
        elif not lower_href.endswith(".xhtml") and not PurePosixPath(normalized).suffix:
            normalized = f"{normalized}.xhtml"

        return normalized

    def _relative_asset_prefix(self, chapter_href: str, folder_name: str) -> str:
        chapter_path = PurePosixPath(str(chapter_href))
        depth = len(chapter_path.parts) - 1
        if depth <= 0:
            return folder_name
        return "/".join([".."] * depth + [folder_name])
