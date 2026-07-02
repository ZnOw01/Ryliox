from __future__ import annotations

import pytest

from plugins.downloader import DownloaderPlugin


@pytest.mark.integration
class TestDownloaderFormatsInfo:
    def test_pdf_supports_chapter_selection(self):
        formats_info = DownloaderPlugin.get_formats_info()

        assert formats_info["book_only"] == ["epub"]
        assert DownloaderPlugin.supports_chapter_selection("epub") is False
        assert DownloaderPlugin.supports_chapter_selection("pdf") is True
        assert DownloaderPlugin.supports_chapter_selection("pdf-chapters") is True
