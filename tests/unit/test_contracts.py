from __future__ import annotations

import pytest

from core.contracts import BookInfo, ChapterInfo, ChapterSummary, FormatInfo

pytestmark = pytest.mark.unit


class TestBookInfo:
    def test_construction_with_all_fields(self):
        book: BookInfo = {
            "book_id": "9780134685991",
            "title": "Effective Python",
            "authors": ["Brett Slatkin"],
            "publisher": "Addison-Wesley Professional",
            "cover_url": "https://example.com/cover.jpg",
            "description": "A great book",
            "isbn": "9780134685991",
            "topics": ["Python", "Programming"],
            "pages": 320,
        }
        assert book["book_id"] == "9780134685991"
        assert book["title"] == "Effective Python"
        assert book["authors"] == ["Brett Slatkin"]
        assert book["publisher"] == "Addison-Wesley Professional"
        assert book["cover_url"] == "https://example.com/cover.jpg"
        assert book["description"] == "A great book"
        assert book["isbn"] == "9780134685991"
        assert book["topics"] == ["Python", "Programming"]
        assert book["pages"] == 320

    def test_construction_with_minimal_fields(self):
        book: BookInfo = {"book_id": "123", "title": "Minimal Book"}
        assert book["book_id"] == "123"
        assert book["title"] == "Minimal Book"

    def test_total_false_allows_partial_fields(self):
        book: BookInfo = {"book_id": "123"}
        assert book["book_id"] == "123"
        assert "title" not in book

    def test_cover_url_can_be_none(self):
        book: BookInfo = {
            "book_id": "1",
            "title": "Test",
            "cover_url": None,
        }
        assert book["cover_url"] is None

    def test_isbn_can_be_none(self):
        book: BookInfo = {"book_id": "1", "title": "Test", "isbn": None}
        assert book["isbn"] is None

    def test_pages_can_be_none(self):
        book: BookInfo = {"book_id": "1", "title": "Test", "pages": None}
        assert book["pages"] is None

    def test_authors_defaults_to_empty_list(self):
        book: BookInfo = {"book_id": "1", "title": "Test"}
        assert book.get("authors", []) == []

    def test_topics_defaults_to_empty_list(self):
        book: BookInfo = {"book_id": "1", "title": "Test"}
        assert book.get("topics", []) == []

    def test_mutable_dict_can_update_field(self):
        book: BookInfo = {"book_id": "1", "title": "Old"}
        book["title"] = "New"
        assert book["title"] == "New"

    def test_mutable_dict_can_add_field(self):
        book: BookInfo = {"book_id": "1"}
        book["title"] = "Added"
        assert book["title"] == "Added"

    def test_multiple_authors(self):
        book: BookInfo = {
            "book_id": "1",
            "title": "Team Book",
            "authors": ["Alice", "Bob", "Charlie"],
        }
        assert len(book["authors"]) == 3

    def test_cover_url_with_optional_field_missing(self):
        book: BookInfo = {"book_id": "1", "title": "No Cover"}
        assert "cover_url" not in book


class TestChapterInfo:
    def test_construction_with_all_fields(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:abc123",
            "title": "Introduction",
            "filename": "ch01.html",
            "content_url": "https://example.com/ch01",
            "images": ["img1.png", "img2.png"],
            "stylesheets": ["style.css"],
            "virtual_pages": 10,
            "minutes_required": 15.5,
        }
        assert chapter["ourn"] == "urn:orm:chapter:abc123"
        assert chapter["title"] == "Introduction"
        assert chapter["filename"] == "ch01.html"
        assert chapter["content_url"] == "https://example.com/ch01"
        assert chapter["images"] == ["img1.png", "img2.png"]
        assert chapter["stylesheets"] == ["style.css"]
        assert chapter["virtual_pages"] == 10
        assert chapter["minutes_required"] == 15.5

    def test_virtual_pages_can_be_none(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:1",
            "title": "Intro",
            "filename": "intro.html",
            "content_url": "https://example.com/intro",
            "images": [],
            "stylesheets": [],
            "virtual_pages": None,
            "minutes_required": None,
        }
        assert chapter["virtual_pages"] is None

    def test_minutes_required_can_be_none(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:1",
            "title": "Intro",
            "filename": "intro.html",
            "content_url": "https://example.com/intro",
            "images": [],
            "stylesheets": [],
            "virtual_pages": 5,
            "minutes_required": None,
        }
        assert chapter["minutes_required"] is None

    def test_float_minutes_required(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:1",
            "title": "Long Chapter",
            "filename": "long.html",
            "content_url": "https://example.com/long",
            "images": [],
            "stylesheets": [],
            "virtual_pages": 30,
            "minutes_required": 45.75,
        }
        assert chapter["minutes_required"] == 45.75

    def test_empty_images_list(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:1",
            "title": "No Images",
            "filename": "noimg.html",
            "content_url": "https://example.com/noimg",
            "images": [],
            "stylesheets": ["style.css"],
            "virtual_pages": 1,
            "minutes_required": 1.0,
        }
        assert chapter["images"] == []

    def test_empty_stylesheets_list(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:1",
            "title": "No Styles",
            "filename": "nostyle.html",
            "content_url": "https://example.com/nostyle",
            "images": [],
            "stylesheets": [],
            "virtual_pages": 1,
            "minutes_required": 1.0,
        }
        assert chapter["stylesheets"] == []

    def test_mutable_fields(self):
        chapter: ChapterInfo = {
            "ourn": "urn:orm:chapter:1",
            "title": "Original",
            "filename": "orig.html",
            "content_url": "url",
            "images": [],
            "stylesheets": [],
            "virtual_pages": 1,
            "minutes_required": 1.0,
        }
        chapter["title"] = "Updated"
        assert chapter["title"] == "Updated"


class TestChapterSummary:
    def test_construction_with_all_fields(self):
        summary: ChapterSummary = {
            "index": 0,
            "title": "Introduction",
            "pages": 10,
            "minutes": 15.5,
        }
        assert summary["index"] == 0
        assert summary["title"] == "Introduction"
        assert summary["pages"] == 10
        assert summary["minutes"] == 15.5

    def test_pages_can_be_none(self):
        summary: ChapterSummary = {"index": 0, "title": "Intro", "pages": None, "minutes": None}
        assert summary["pages"] is None
        assert summary["minutes"] is None

    def test_minutes_float(self):
        summary: ChapterSummary = {
            "index": 1,
            "title": "Advanced",
            "pages": 25,
            "minutes": 30.0,
        }
        assert summary["minutes"] == 30.0


class TestFormatInfo:
    def test_construction_with_all_fields(self):
        fmt: FormatInfo = {
            "name": "epub",
            "description": "EPUB format",
            "supports_chapters": True,
            "aliases": ["epub", "e-book"],
        }
        assert fmt["name"] == "epub"
        assert fmt["description"] == "EPUB format"
        assert fmt["supports_chapters"] is True
        assert fmt["aliases"] == ["epub", "e-book"]

    def test_supports_chapters_false(self):
        fmt: FormatInfo = {
            "name": "pdf",
            "description": "PDF format",
            "supports_chapters": False,
            "aliases": ["pdf"],
        }
        assert fmt["supports_chapters"] is False

    def test_multiple_aliases(self):
        fmt: FormatInfo = {
            "name": "mobi",
            "description": "Mobipocket format",
            "supports_chapters": False,
            "aliases": ["mobi", "mobipocket", "kindle"],
        }
        assert len(fmt["aliases"]) == 3

    def test_single_alias(self):
        fmt: FormatInfo = {
            "name": "txt",
            "description": "Plain text",
            "supports_chapters": False,
            "aliases": ["text"],
        }
        assert fmt["aliases"] == ["text"]

    def test_mutable_fields(self):
        fmt: FormatInfo = {
            "name": "original",
            "description": "Original",
            "supports_chapters": True,
            "aliases": ["orig"],
        }
        fmt["name"] = "updated"
        assert fmt["name"] == "updated"
