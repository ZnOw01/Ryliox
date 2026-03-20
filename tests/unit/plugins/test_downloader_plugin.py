from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from plugins.downloader import DownloaderPlugin

pytestmark = pytest.mark.unit


class DummyBookPlugin:
    async def fetch(self, _book_id: str) -> dict[str, object]:
        return {"title": "Demo", "authors": ["Author"]}


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


def test_normalize_asset_url_blocks_external_hosts():
    plugin = DownloaderPlugin()

    assert plugin._normalize_asset_url("", "https://example.com/file.png") == ""


def test_normalize_asset_url_allows_subdomains_of_base_host():
    plugin = DownloaderPlugin()

    assert (
        plugin._normalize_asset_url(
            "", "https://cdn.learning.oreilly.com/assets/file.png"
        )
        == "https://cdn.learning.oreilly.com/assets/file.png"
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
            formats=["epub"],
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
