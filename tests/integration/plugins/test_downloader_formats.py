from __future__ import annotations

import pytest

from plugins.downloader import DownloaderPlugin


@pytest.mark.integration
class TestDownloaderFormatsInfo:
    def test_pdf_is_book_only_format(self):
        formats_info = DownloaderPlugin.get_formats_info()

        assert "pdf" in formats_info["book_only"]
        assert DownloaderPlugin.supports_chapter_selection("pdf") is False
        assert DownloaderPlugin.supports_chapter_selection("pdf-chapters") is True
