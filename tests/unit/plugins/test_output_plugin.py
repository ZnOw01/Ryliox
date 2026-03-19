from __future__ import annotations

from pathlib import Path

import pytest

from plugins.output import OutputPlugin

pytestmark = pytest.mark.unit


def test_validate_dir_creates_missing_directory(tmp_path: Path):
    plugin = OutputPlugin()
    target = tmp_path / "new-output"

    valid, message, resolved = plugin.validate_dir(target)

    assert valid is True
    assert message == "Directory is valid"
    assert resolved == target
    assert target.exists()
    assert target.is_dir()


def test_create_book_dir_creates_expected_structure(tmp_path: Path):
    plugin = OutputPlugin()

    book_dir = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="demo-book",
        title="A Demo Book",
        authors=["Author One"],
    )

    assert book_dir.exists()
    assert (book_dir / "OEBPS").is_dir()
    assert (book_dir / ".book_id").read_text(encoding="utf-8") == "demo-book"


def test_create_book_dir_uses_unique_suffix_for_collisions(tmp_path: Path):
    plugin = OutputPlugin()

    first = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="book-1",
        title="Repeated Title",
        authors=None,
    )
    second = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="book-2",
        title="Repeated Title",
        authors=None,
    )

    assert first != second
    assert first.name == "repeated-title"
    assert second.name == "repeated-title-2"
