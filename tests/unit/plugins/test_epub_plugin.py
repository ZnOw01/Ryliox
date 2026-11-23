from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from plugins.epub import EpubPlugin

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def test_create_epub_zip_excludes_non_epub_artifacts(tmp_path: Path):
    plugin = EpubPlugin()

    (tmp_path / "mimetype").write_text("application/epub+zip", encoding="utf-8")
    (tmp_path / "META-INF").mkdir()
    (tmp_path / "OEBPS").mkdir()
    (tmp_path / "META-INF" / "container.xml").write_text("<container />", encoding="utf-8")
    (tmp_path / "OEBPS" / "chapter.xhtml").write_text("<html />", encoding="utf-8")
    (tmp_path / "OEBPS" / "stale.pdf").write_text("ignore me", encoding="utf-8")

    plugin._create_epub_zip(tmp_path, tmp_path / "book.epub")

    with zipfile.ZipFile(tmp_path / "book.epub") as zf:
        names = zf.namelist()

    assert names[0] == "mimetype"
    assert "META-INF/container.xml" in names
    assert "OEBPS/chapter.xhtml" in names
    assert "OEBPS/stale.pdf" not in names


def test_write_content_opf_escapes_text_once(tmp_path: Path):
    plugin = EpubPlugin()
    oebps = tmp_path / "OEBPS"
    oebps.mkdir()

    plugin._write_content_opf(
        oebps=oebps,
        book_info={
            "title": "A & B",
            "authors": ["X & Y"],
            "description": "Summary with <tags> & symbols",
            "language": "en",
            "isbn": "12345",
            "publication_date": "2026-01-01",
        },
        chapter_entries=[],
        css_files=[],
        cover_image=None,
    )

    content = (oebps / "content.opf").read_text(encoding="utf-8")

    assert "<dc:title>A &amp; B</dc:title>" in content
    assert "<dc:creator>X &amp; Y</dc:creator>" in content
    assert "&amp;amp;" not in content


def test_validate_manifest_files_rejects_missing_chapter(tmp_path: Path):
    plugin = EpubPlugin()
    oebps = tmp_path / "OEBPS"
    oebps.mkdir()
    (oebps / "chapter01.xhtml").write_text("<html />", encoding="utf-8")

    with pytest.raises(RuntimeError, match="chapter02.xhtml"):
        plugin._validate_manifest_files(
            oebps,
            [
                {"filename": "chapter01.html"},
                {"filename": "chapter02.html"},
            ],
        )


def test_write_content_opf_has_no_empty_required_metadata(tmp_path: Path):
    # The book plugin reports a missing ISBN, date or description as "".
    oebps = tmp_path / "OEBPS"
    (oebps / "Images").mkdir(parents=True)
    (oebps / "Images" / "pic.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")

    EpubPlugin()._write_content_opf(
        oebps=oebps,
        book_info={"id": "9781", "isbn": "", "description": "", "publication_date": ""},
        chapter_entries=[],
    )

    opf = (oebps / "content.opf").read_text(encoding="utf-8")
    assert '<dc:identifier id="bookid">9781</dc:identifier>' in opf
    assert "<dc:description>" not in opf
    assert "<dc:date>" not in opf
    assert 'href="Images/pic.webp" media-type="image/webp"' in opf


def test_resolve_internal_links_keeps_subfolders(tmp_path: Path):
    oebps = tmp_path / "OEBPS"
    (oebps / "text").mkdir(parents=True)
    (oebps / "notes").mkdir()
    page = '<html xmlns="http://www.w3.org/1999/xhtml"><body>{}</body></html>'
    (oebps / "text" / "ch.xhtml").write_text(
        page.format(
            '<a id="ref1" href="../notes/fn.xhtml#n1">1</a>'
            '<a href="#missing">gone</a>'
            '<a href="https://example.com/x.html#n1">web</a>'
        ),
        encoding="utf-8",
    )
    (oebps / "notes" / "fn.xhtml").write_text(
        page.format('<p id="n1"><a href="ch.xhtml#ref1">back</a></p>'), encoding="utf-8"
    )
    (oebps / "nav.xhtml").write_text(
        page.format('<a href="ch.xhtml#ref1">Chapter</a>'), encoding="utf-8"
    )
    (oebps / "toc.ncx").write_text(
        '<ncx><navMap><navPoint><content src="fn.xhtml#n1"/></navPoint></navMap></ncx>',
        encoding="utf-8",
    )

    EpubPlugin()._resolve_internal_links(oebps)

    chapter = (oebps / "text" / "ch.xhtml").read_text(encoding="utf-8")
    assert 'href="../notes/fn.xhtml#n1"' in chapter
    assert 'href=""' in chapter
    assert 'href="https://example.com/x.html#n1"' in chapter
    notes = (oebps / "notes" / "fn.xhtml").read_text(encoding="utf-8")
    assert 'href="../text/ch.xhtml#ref1"' in notes
    assert 'href="text/ch.xhtml#ref1"' in (oebps / "nav.xhtml").read_text(encoding="utf-8")
    assert 'src="notes/fn.xhtml#n1"' in (oebps / "toc.ncx").read_text(encoding="utf-8")


@pytest.mark.parametrize(("language", "expected"), [("ja", "ja"), ('en"><x', "en")])
def test_write_content_opf_validates_language(tmp_path: Path, language: str, expected: str):
    oebps = tmp_path / "OEBPS"
    oebps.mkdir()

    EpubPlugin()._write_content_opf(
        oebps=oebps, book_info={"id": "9781", "language": language}, chapter_entries=[]
    )

    opf = (oebps / "content.opf").read_text(encoding="utf-8")
    assert f"<dc:language>{expected}</dc:language>" in opf


def test_write_content_opf_description_is_plain_text_cut_at_a_word(tmp_path: Path):
    # O'Reilly sends the description as HTML, often longer than the 500-char cap.
    oebps = tmp_path / "OEBPS"
    oebps.mkdir()
    raw = (
        "<span><div><p><i>Book</i> is a guide &amp; more.</p><p>"
        + "word " * 200
        + "</p></div></span>"
    )

    EpubPlugin()._write_content_opf(
        oebps=oebps, book_info={"id": "9781", "description": raw}, chapter_entries=[]
    )

    opf = (oebps / "content.opf").read_text(encoding="utf-8")
    description = opf.split("<dc:description>")[1].split("</dc:description>")[0]
    assert description.startswith("Book is a guide &amp; more. word word")
    assert "&lt;" not in description
    assert description.endswith("word…")
    assert len(description) <= 510
