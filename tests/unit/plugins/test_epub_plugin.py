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
