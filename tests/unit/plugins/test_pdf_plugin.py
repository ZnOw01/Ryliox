from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from plugins.pdf import PdfPlugin

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def test_images_of_a_chapter_in_a_subfolder_resolve_from_the_book_root(tmp_path: Path):
    # The PDF puts every chapter in one document based at OEBPS/, so the
    # ``../Images/`` the downloader writes for Text/ch01.xhtml must be rebased.
    oebps = tmp_path / "OEBPS"
    (oebps / "Text").mkdir(parents=True)
    (oebps / "Text" / "ch01.xhtml").write_text(
        '<html><body><img src="../Images/fig.png"/><img src="data:image/png;base64,AA"/>'
        '<img src="https://example.com/x.png"/></body></html>',
        encoding="utf-8",
    )
    (oebps / "ch02.xhtml").write_text(
        '<html><body><img src="Images/b.png"/></body></html>', encoding="utf-8"
    )

    html = PdfPlugin()._build_combined_html(
        book_info={"title": "T"},
        chapters=[{"filename": "Text/ch01.html"}, {"filename": "ch02.html"}],
        toc=[],
        oebps=oebps,
        css_files=[],
        cover_image=None,
    )

    assert 'src="Images/fig.png"' in html
    assert 'src="data:image/png;base64,AA"' in html
    assert 'src="https://example.com/x.png"' in html
    assert 'src="Images/b.png"' in html
