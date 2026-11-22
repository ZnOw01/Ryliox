from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING
from xml.etree import ElementTree

import pytest

from core.dto import DownloadJobDTO, DownloadResultDTO
from core.repository import DownloadJobRepository
from plugins.downloader import DownloaderPlugin
from plugins.epub import EpubPlugin

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def _chapter(filename: str, title: str) -> dict[str, object]:
    return {
        "ourn": f"urn:orm:chapter:{title}",
        "title": title,
        "filename": filename,
        "content_url": f"https://learning.oreilly.com/{filename}",
        "images": [],
        "stylesheets": [],
        "virtual_pages": None,
        "minutes_required": None,
    }


class StubBookPlugin:
    async def fetch(self, book_id: str) -> dict[str, object]:
        return {"id": book_id, "title": "Phase 1", "authors": ["Test Author"]}


class StubChaptersPlugin:
    def __init__(
        self,
        chapters: list[dict[str, object]],
        reordered: list[dict[str, object]] | None = None,
    ) -> None:
        self._chapters = chapters
        self._reordered = reordered

    async def fetch_list(self, _book_id: str) -> list[dict[str, object]]:
        return self._chapters

    async def fetch_toc(self, _book_id: str) -> list[dict[str, object]]:
        return []

    def reorder_by_toc(
        self,
        chapters: list[dict[str, object]],
        _toc: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return self._reordered if self._reordered is not None else chapters

    async def fetch_content(self, _content_url: str) -> str:
        return "<p>Chapter body</p>"


class StubAssetsPlugin:
    async def download_all_css(self, *_args: object, **_kwargs: object) -> dict[str, Path]:
        return {}

    async def download_css_assets(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def download_all_images(self, *_args: object, **_kwargs: object) -> dict[str, Path]:
        return {}


class StubHtmlProcessorPlugin:
    def process(self, html: str, *_args: object, **_kwargs: object) -> tuple[str, list[str]]:
        return html, []

    def wrap_xhtml(self, content: str, _css_files: list[str], title: str = "") -> str:
        return f"<html><head><title>{title}</title></head><body>{content}</body></html>"

    def inline_css_content_images(self, _oebps: Path) -> None:
        return None


class StubOutputPlugin:
    def create_book_dir(self, output_dir: Path, **_kwargs: object) -> Path:
        book_dir = output_dir / "phase-1"
        (book_dir / "OEBPS").mkdir(parents=True)
        return book_dir

    def get_oebps_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS"

    def get_images_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS" / "Images"


class ObservingPdfPlugin:
    def __init__(self) -> None:
        self.chapter_titles: list[str] = []

    def generate(
        self,
        *,
        output_dir: Path,
        chapters: list[dict[str, object]],
        **_kwargs: object,
    ) -> Path:
        self.chapter_titles = [str(chapter["title"]) for chapter in chapters]
        for chapter in chapters:
            chapter_path = (
                output_dir / "OEBPS" / str(chapter["filename"]).replace(".html", ".xhtml")
            )
            assert chapter_path.is_file(), f"PDF generation cannot access {chapter_path}"
        pdf_path = output_dir / "phase-1.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        return pdf_path


def _downloader(
    chapters_plugin: StubChaptersPlugin,
    *,
    epub_plugin: object | None = None,
    pdf_plugin: object | None = None,
) -> DownloaderPlugin:
    return DownloaderPlugin(
        book_plugin=StubBookPlugin(),
        chapters_plugin=chapters_plugin,
        assets_plugin=StubAssetsPlugin(),
        html_processor_plugin=StubHtmlProcessorPlugin(),
        output_plugin=StubOutputPlugin(),
        epub_plugin=epub_plugin,
        pdf_plugin=pdf_plugin,
    )


@pytest.mark.asyncio
async def test_epub_and_pdf_generation_keeps_oebps_available_to_pdf(tmp_path: Path) -> None:
    chapter = _chapter("chapter-1.html", "Chapter 1")
    pdf_plugin = ObservingPdfPlugin()
    downloader = _downloader(
        StubChaptersPlugin([chapter]),
        epub_plugin=EpubPlugin(),
        pdf_plugin=pdf_plugin,
    )

    result = await downloader.download(
        book_id="phase-1",
        output_dir=tmp_path,
        formats=["epub", "pdf"],
        skip_images=True,
    )

    assert isinstance(result.files["epub"], str)
    assert result.files["epub"].endswith(".epub")
    assert isinstance(result.files["pdf"], str)
    assert result.files["pdf"].endswith(".pdf")
    assert pdf_plugin.chapter_titles == ["Chapter 1"]


def test_mark_completed_rejects_job_with_cancel_requested(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "downloads.db")
    job = DownloadJobDTO(
        job_id="cancel-before-complete",
        book_id="phase-1",
        output_dir=tmp_path,
        formats=["epub"],
    )
    result = DownloadResultDTO(
        book_id="phase-1",
        title="Phase 1",
        epub_path=str(tmp_path / "phase-1.epub"),
        chapters_count=1,
    )

    try:
        repository.save(job)
        assert repository.claim_next_queued() is not None
        cancel_status, _snapshot = repository.request_cancel(job.job_id)

        completed = repository.mark_completed(job.job_id, result)

        assert cancel_status == "cancel_requested"
        assert completed is False
        assert repository.is_cancel_requested(job.job_id) is True
        snapshot = repository.get_by_id(job.job_id)
        assert snapshot is not None
        assert snapshot["status"] == "starting"
    finally:
        repository.close()


@pytest.mark.asyncio
async def test_selected_chapter_indexes_apply_to_final_reordered_chapters(
    tmp_path: Path,
) -> None:
    first = _chapter("first.html", "First from API")
    second = _chapter("second.html", "First in final order")
    chapters_plugin = StubChaptersPlugin([first, second], reordered=[second, first])
    pdf_plugin = ObservingPdfPlugin()
    downloader = _downloader(chapters_plugin, pdf_plugin=pdf_plugin)

    result = await downloader.download(
        book_id="phase-1",
        output_dir=tmp_path,
        formats=["pdf"],
        selected_chapters=[0],
        skip_images=True,
    )

    assert result.chapters_count == 1
    assert pdf_plugin.chapter_titles == ["First in final order"]


def test_epub_manifest_declares_cover_image(tmp_path: Path) -> None:
    oebps = tmp_path / "OEBPS"
    images = oebps / "Images"
    images.mkdir(parents=True)
    (oebps / "chapter.xhtml").write_text("<html />", encoding="utf-8")
    (images / "cover.jpg").write_bytes(b"fake-jpeg")

    epub_path = EpubPlugin().generate(
        book_info={"id": "phase-1", "title": "Phase 1"},
        chapters=[{"filename": "chapter.html"}],
        toc=[],
        output_dir=tmp_path,
        css_files=[],
        cover_image="cover.jpg",
    )

    with zipfile.ZipFile(epub_path) as archive:
        content_opf = archive.read("OEBPS/content.opf")
    package = ElementTree.fromstring(content_opf)
    manifest_items = package.findall(
        ".//{http://www.idpf.org/2007/opf}manifest/{http://www.idpf.org/2007/opf}item"
    )

    cover_items = [item for item in manifest_items if item.get("href") == "Images/cover.jpg"]
    assert len(cover_items) == 1
    assert cover_items[0].get("properties") == "cover-image"


@pytest.mark.asyncio
async def test_chapter_filename_cannot_escape_oebps(tmp_path: Path) -> None:
    chapter = _chapter("../escaped.html", "Traversal")
    downloader = _downloader(
        StubChaptersPlugin([chapter]),
        pdf_plugin=ObservingPdfPlugin(),
    )

    with pytest.raises(ValueError):
        await downloader.download(
            book_id="phase-1",
            output_dir=tmp_path,
            formats=["pdf"],
            skip_images=True,
        )

    assert not (tmp_path / "phase-1" / "escaped.xhtml").exists()
