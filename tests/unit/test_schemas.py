"""Unit tests for Pydantic schemas.

Tests cover:
- Request model validation
- Response model creation
- Format validation
- Edge cases
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from web.schemas import (
    BookChaptersResponse,
    BookInfoResponse,
    CancelRequest,
    ChapterSummaryResponse,
    CookiesResponse,
    DownloadRequest,
    DownloadStartResponse,
    ErrorResponse,
    SearchResponse,
    StatusResponse,
    _RequestModel,
    _ResponseModel,
)


class TestBaseModels:
    """Tests for base model classes."""

    def test_request_model_rejects_extra_fields(self):
        """Test that request models reject extra fields."""

        class TestRequest(_RequestModel):
            name: str

        # Should reject extra fields
        with pytest.raises(ValidationError):
            TestRequest(name="test", extra_field="value")

    def test_response_model_ignores_extra_fields(self):
        """Test that response models ignore extra fields."""

        class TestResponse(_ResponseModel):
            name: str

        # Should ignore extra fields
        response = TestResponse(name="test", extra_field="value")
        assert response.name == "test"


class TestDownloadRequest:
    """Tests for DownloadRequest schema."""

    def test_valid_download_request(self):
        """Test creating a valid download request."""
        request = DownloadRequest(
            book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff",
            format=["epub"],
            chapters=[0, 1, 2],
            output_dir="/tmp/output",
            skip_images=True,
        )

        assert request.book_id == "urn:orm:book:aabbccddeeff00112233aabbccddeeff"
        assert request.format == ["epub"]
        assert request.chapters == [0, 1, 2]
        assert request.output_dir == "/tmp/output"
        assert request.skip_images is True

    def test_default_format_is_epub(self):
        """Test that default format is epub."""
        request = DownloadRequest(book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff")

        assert request.format == ["epub"]

    def test_format_string_normalization(self):
        """Test that string format is normalized to list."""
        request = DownloadRequest(
            book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff", format="pdf"
        )

        assert request.format == ["pdf"]

    def test_format_empty_string_error(self):
        """Test that empty string format raises error."""
        with pytest.raises(ValidationError):
            DownloadRequest(book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff", format="")

    def test_format_list_normalization(self):
        """Test that tuple and set are normalized to list."""
        request = DownloadRequest(
            book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff",
            format=("epub", "pdf"),
        )

        assert request.format == ["epub", "pdf"]

    def test_format_invalid_type_error(self):
        """Test that invalid format type raises error."""
        with pytest.raises(ValidationError):
            DownloadRequest(book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff", format=123)

    def test_negative_chapter_indexes_error(self):
        """Test that negative chapter indexes raise error."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadRequest(
                book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff",
                chapters=[-1, 0, 1],
            )

        assert "Invalid chapter indexes" in str(exc_info.value)

    def test_empty_chapters_allowed(self):
        """Test that empty chapters list is allowed."""
        request = DownloadRequest(
            book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff", chapters=[]
        )

        assert request.chapters == []

    def test_none_chapters_allowed(self):
        """Test that None chapters is allowed."""
        request = DownloadRequest(
            book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff", chapters=None
        )

        assert request.chapters is None

    def test_book_id_min_length(self):
        """Test book_id minimum length validation."""
        with pytest.raises(ValidationError):
            DownloadRequest(book_id="ab")  # Too short (min 10 chars) and wrong format

    def test_book_id_wrong_format(self):
        """Test book_id format validation for non-urn format."""
        with pytest.raises(ValidationError):
            DownloadRequest(book_id="9780134685991")  # ISBN without urn:orm:book: prefix

    def test_output_dir_min_length(self):
        """Test output_dir minimum length validation."""
        with pytest.raises(ValidationError):
            DownloadRequest(book_id="urn:orm:book:aabbccddeeff00112233aabbccddeeff", output_dir="")


class TestCancelRequest:
    """Tests for CancelRequest schema."""

    def test_valid_cancel_request(self):
        """Test creating a valid cancel request."""
        request = CancelRequest(job_id="abc-123-def")

        assert request.job_id == "abc-123-def"

    def test_cancel_request_optional_job_id(self):
        """Test that job_id is optional."""
        request = CancelRequest()

        assert request.job_id is None

    def test_cancel_request_empty_string_not_allowed(self):
        """Test that empty string job_id is not allowed."""
        with pytest.raises(ValidationError):
            CancelRequest(job_id="")


class TestBookInfoResponse:
    """Tests for BookInfoResponse schema."""

    def test_valid_book_info(self):
        """Test creating valid book info response."""
        book = BookInfoResponse(
            id="9780134685991",
            title="Effective Python",
            isbn="9780134685991",
            virtual_pages=320,
        )

        assert book.id == "9780134685991"
        assert book.title == "Effective Python"
        assert book.virtual_pages == 320

    def test_default_lists_empty(self):
        """Test that lists default to empty."""
        book = BookInfoResponse(id="test123")

        assert book.authors == []
        assert book.publishers == []

    def test_virtual_pages_must_be_positive(self):
        """Test that virtual_pages must be >= 0."""
        with pytest.raises(ValidationError):
            BookInfoResponse(id="test123", virtual_pages=-1)

    def test_optional_fields_none(self):
        """Test that optional fields can be None."""
        book = BookInfoResponse(id="test123")

        assert book.title is None
        assert book.isbn is None
        assert book.description is None


class TestChapterSummaryResponse:
    """Tests for ChapterSummaryResponse schema."""

    def test_valid_chapter(self):
        """Test creating valid chapter response."""
        chapter = ChapterSummaryResponse(
            index=0,
            title="Introduction",
            pages=10,
            minutes=15.5,
        )

        assert chapter.index == 0
        assert chapter.title == "Introduction"
        assert chapter.pages == 10
        assert chapter.minutes == 15.5

    def test_pages_must_be_positive(self):
        """Test that pages must be >= 1."""
        with pytest.raises(ValidationError):
            ChapterSummaryResponse(index=0, title="Test", pages=0)

    def test_minutes_must_be_positive(self):
        """Test that minutes must be >= 0."""
        with pytest.raises(ValidationError):
            ChapterSummaryResponse(index=0, title="Test", minutes=-1)

    def test_optional_fields_none(self):
        """Test that pages and minutes can be None."""
        chapter = ChapterSummaryResponse(index=0, title="Test")

        assert chapter.pages is None
        assert chapter.minutes is None


class TestBookChaptersResponse:
    """Tests for BookChaptersResponse schema."""

    def test_valid_chapters_response(self):
        """Test creating valid chapters response."""
        chapters = [
            ChapterSummaryResponse(index=0, title="Chapter 1"),
            ChapterSummaryResponse(index=1, title="Chapter 2"),
        ]
        response = BookChaptersResponse(chapters=chapters)

        assert response.chapters == chapters
        assert response.total == 2

    def test_computed_total_field(self):
        """Test that total field is computed from chapters."""
        chapters = [
            ChapterSummaryResponse(index=0, title="Chapter 1"),
            ChapterSummaryResponse(index=1, title="Chapter 2"),
            ChapterSummaryResponse(index=2, title="Chapter 3"),
        ]
        response = BookChaptersResponse(chapters=chapters)

        assert response.total == 3

    def test_empty_chapters(self):
        """Test response with empty chapters."""
        response = BookChaptersResponse(chapters=[])

        assert response.total == 0


class TestDownloadStartResponse:
    """Tests for DownloadStartResponse schema."""

    def test_valid_response(self):
        """Test creating valid download start response."""
        response = DownloadStartResponse(
            status="queued",
            book_id="9780134685991",
            job_id="abc-123",
            queue_position=1,
        )

        assert response.status == "queued"
        assert response.book_id == "9780134685991"
        assert response.job_id == "abc-123"
        assert response.queue_position == 1

    def test_optional_fields_none(self):
        """Test that optional fields can be None."""
        response = DownloadStartResponse(
            status="queued",
            job_id="abc-123",
        )

        assert response.book_id is None
        assert response.queue_position is None

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # job_id is required
        with pytest.raises(ValidationError):
            DownloadStartResponse(status="queued")


class TestStatusResponse:
    """Tests for StatusResponse schema."""

    def test_valid_response(self):
        """Test creating valid status response."""
        response = StatusResponse(
            valid=True,
            reason=None,
            has_cookies=True,
        )

        assert response.valid is True
        assert response.reason is None
        assert response.has_cookies is True

    def test_valid_with_reason(self):
        """Test valid=False with reason."""
        response = StatusResponse(
            valid=False,
            reason="no_session",
            has_cookies=False,
        )

        assert response.valid is False
        assert response.reason == "no_session"


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_valid_error(self):
        """Test creating valid error response."""
        error = ErrorResponse(
            error="Book not found",
            code="BOOK_NOT_FOUND",
            details={"book_id": "123"},
        )

        assert error.error == "Book not found"
        assert error.code == "BOOK_NOT_FOUND"
        assert error.details == {"book_id": "123"}

    def test_details_optional(self):
        """Test that details is optional."""
        error = ErrorResponse(
            error="Generic error",
            code="GENERIC_ERROR",
        )

        assert error.details is None


class TestSearchResponse:
    """Tests for SearchResponse schema."""

    def test_valid_response(self):
        """Test creating valid search response."""
        results = [
            {"id": "1", "title": "Book 1"},
            {"id": "2", "title": "Book 2"},
        ]
        response = SearchResponse(results=results)

        assert response.results == results

    def test_empty_results(self):
        """Test response with empty results."""
        response = SearchResponse(results=[])

        assert response.results == []


class TestCookiesResponse:
    """Tests for CookiesResponse schema."""

    def test_valid_response(self):
        """Test creating valid cookies response."""
        cookies = {"session": "abc123", "auth": "token"}
        response = CookiesResponse(cookies=cookies)

        assert response.cookies == cookies

    def test_empty_cookies(self):
        """Test response with empty cookies."""
        response = CookiesResponse(cookies={})

        assert response.cookies == {}


class TestSchemaEdgeCases:
    """Edge case tests for schemas."""

    def test_unicode_in_strings(self):
        """Test that unicode strings are accepted."""
        book = BookInfoResponse(
            id="test",
            title="测试书籍",
            description="这是一本关于Python的书",
        )

        assert book.title == "测试书籍"

    def test_very_long_strings(self):
        """Test handling of very long strings."""
        long_title = "A" * 10000
        book = BookInfoResponse(id="test", title=long_title)

        assert book.title == long_title

    def test_special_characters_in_strings(self):
        """Test handling of special characters."""
        special_title = "<script>alert('test')</script>"
        book = BookInfoResponse(id="test", title=special_title)

        # Schema accepts any string, sanitization happens elsewhere
        assert book.title == special_title

    def test_extra_fields_ignored_in_response(self):
        """Test that extra fields are ignored in response models."""
        book = BookInfoResponse(
            id="test",
            title="Test Book",
            extra_field_1="value1",
            extra_field_2="value2",
        )

        # Should not have extra fields
        assert not hasattr(book, "extra_field_1")
        assert not hasattr(book, "extra_field_2")
