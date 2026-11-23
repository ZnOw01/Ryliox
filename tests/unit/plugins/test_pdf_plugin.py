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


@pytest.mark.parametrize(("language", "expected"), [("de", "de"), (None, "en"), ("<bad>", "en")])
def test_pdf_html_declares_the_book_language(tmp_path: Path, language: str | None, expected: str):
    oebps = tmp_path / "OEBPS"
    oebps.mkdir()
    (oebps / "ch01.xhtml").write_text("<html><body><p>Text</p></body></html>", encoding="utf-8")

    html = PdfPlugin()._build_combined_html(
        book_info={"title": "T", "language": language},
        chapters=[{"filename": "ch01.html"}],
        toc=[],
        oebps=oebps,
        css_files=[],
        cover_image=None,
    )

    assert f'<html lang="{expected}">' in html


def test_pdf_chapters_declare_the_book_language(tmp_path: Path):
    oebps = tmp_path / "OEBPS"
    oebps.mkdir()
    (oebps / "ch01.xhtml").write_text("<html><body><p>Text</p></body></html>", encoding="utf-8")
    rendered: list[str] = []

    class FakeDocument:
        def __init__(self, string: str, **_kwargs: object) -> None:
            rendered.append(string)

        def write_pdf(self, _path: str) -> None:
            return None

    plugin = PdfPlugin()
    plugin._weasyprint = type("FakeWeasyPrint", (), {"HTML": FakeDocument})
    plugin.generate_chapters(
        book_info={"title": "T", "language": "fr"},
        chapters=[{"filename": "ch01.html", "title": "One"}],
        output_dir=tmp_path,
        css_files=[],
    )

    assert len(rendered) == 1
    assert '<html lang="fr">' in rendered[0]
