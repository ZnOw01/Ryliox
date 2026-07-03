from __future__ import annotations

from pathlib import Path

import pytest

from plugins.downloader import DownloaderPlugin

pytestmark = pytest.mark.unit


class DummyBookPlugin:
    async def fetch(self, _book_id: str) -> dict[str, object]:
        return {"title": "Demo", "authors": ["Author"]}


class DummyBookWithCoverPlugin:
    async def fetch(self, _book_id: str) -> dict[str, object]:
        return {
            "title": "Demo",
            "authors": ["Author"],
            "cover_url": "https://learning.oreilly.com/library/cover/demo-book/",
        }


class DummyChaptersPlugin:
    async def fetch_list(self, _book_id: str) -> list[dict[str, str]]:
        return [
            {
                "filename": "chapter-1.xhtml",
                "content_url": "https://learning.oreilly.com/library/view/demo/ch1.xhtml",
                "title": "Chapter 1",
            }
        ]

    async def fetch_toc(self, _book_id: str) -> list[dict[str, str]]:
        return []


class DummyOutputPlugin:
    def create_book_dir(self, **_kwargs):
        raise AssertionError("create_book_dir should not be called for invalid selection")


class DummyEmptyChaptersPlugin:
    async def fetch_list(self, _book_id: str) -> list[dict[str, str]]:
        return []

    async def fetch_toc(self, _book_id: str) -> list[dict[str, str]]:
        return []


class DummySuccessfulOutputPlugin:
    def create_book_dir(self, output_dir: Path, **_kwargs):
        book_dir = output_dir / "demo-book"
        (book_dir / "OEBPS").mkdir(parents=True)
        return book_dir

    def get_oebps_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS"

    def get_images_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS" / "Images"


class DummyAssetsWithDetectedCoverPlugin:
    async def download_image(self, _url: str, save_path: Path) -> Path:
        cover_path = save_path.with_suffix(".jpg")
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(b"fake-jpeg")
        return cover_path

    async def download_all_css(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}

    async def download_css_assets(self, *_args, **_kwargs) -> None:
        return None

    async def download_all_images(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}


class DummyHtmlProcessorPlugin:
    def inline_css_content_images(self, _oebps: Path) -> None:
        return None


class DummyEpubPlugin:
    def __init__(self) -> None:
        self.cover_image: str | None = None

    def generate(self, *, output_dir: Path, cover_image: str | None = None, **_kwargs) -> Path:
        self.cover_image = cover_image
        epub_path = output_dir / "demo.epub"
        epub_path.write_text("epub", encoding="utf-8")
        return epub_path


def test_normalize_asset_url_blocks_external_hosts():
    plugin = DownloaderPlugin()

    assert plugin._normalize_asset_url("", "https://example.com/file.png") == ""


def test_normalize_asset_url_allows_subdomains_of_base_host():
    plugin = DownloaderPlugin()

    assert (
        plugin._normalize_asset_url("", "https://cdn.learning.oreilly.com/assets/file.png")
        == "https://cdn.learning.oreilly.com/assets/file.png"
    )


@pytest.mark.asyncio
async def test_download_rejects_epub_chapter_selection_before_creating_output_dir():
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=object(),
        html_processor_plugin=object(),
        output_plugin=DummyOutputPlugin(),
        epub_plugin=object(),
    )

    with pytest.raises(ValueError, match="Chapter selection not supported for: epub"):
        await plugin.download(
            book_id="demo-book",
            output_dir=Path("/tmp/demo-output"),
            formats=["epub"],
            selected_chapters=[0],
            skip_images=True,
        )


@pytest.mark.asyncio
async def test_download_raises_when_selected_chapters_do_not_match():
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=object(),
        html_processor_plugin=object(),
        output_plugin=DummyOutputPlugin(),
        epub_plugin=object(),
    )

    with pytest.raises(ValueError, match="Selected chapters did not match"):
        await plugin.download(
            book_id="demo-book",
            output_dir=Path("/tmp/demo-output"),
            formats=["pdf-chapters"],
            selected_chapters=[99],
            skip_images=True,
        )


def test_get_formats_info_hides_redundant_pdf_chapters_option_from_ui():
    formats_info = DownloaderPlugin.get_formats_info()

    assert formats_info["formats"] == ["epub", "pdf"]
    assert "pdf-chapters" in formats_info["descriptions"]
    assert formats_info["descriptions"]["pdf"] == (
        "Un solo PDF con el libro completo o con los capitulos seleccionados."
    )


@pytest.mark.asyncio
async def test_download_passes_detected_cover_filename_to_epub(tmp_path):
    epub_plugin = DummyEpubPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookWithCoverPlugin(),
        chapters_plugin=DummyEmptyChaptersPlugin(),
        assets_plugin=DummyAssetsWithDetectedCoverPlugin(),
        html_processor_plugin=DummyHtmlProcessorPlugin(),
        output_plugin=DummySuccessfulOutputPlugin(),
        epub_plugin=epub_plugin,
    )

    await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=False,
    )

    assert epub_plugin.cover_image == "cover.jpg"
