"""Integration tests for Books API endpoints.

Tests cover:
- Book search functionality
- Book metadata retrieval
- Chapter listing
- Error handling for invalid book IDs
- Input validation
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
class TestBookSearch:
    """Tests for GET /api/search endpoint."""

    def test_search_valid_query(self, test_client: TestClient, mock_kernel, sample_search_results):
        """Test search with a valid query string."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=sample_search_results)

        response = test_client.get("/api/search?q=python")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "Effective Python"

    def test_search_empty_query(self, test_client: TestClient, mock_kernel):
        """Test search with empty query returns empty results."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=[])

        response = test_client.get("/api/search?q=")

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    def test_search_missing_query(self, test_client: TestClient, mock_kernel):
        """Test search without query parameter returns empty results."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=[])

        response = test_client.get("/api/search")

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    def test_search_with_legacy_query_param(
        self, test_client: TestClient, mock_kernel, sample_search_results
    ):
        """Test search using legacy 'query' parameter."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=sample_search_results)

        response = test_client.get("/api/search?query=python")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2

    def test_search_query_too_long(self, test_client: TestClient):
        """Test search with query exceeding maximum length."""
        long_query = "a" * 201  # MAX_SEARCH_LENGTH is 200

        response = test_client.get(f"/api/search?q={long_query}")

        assert response.status_code == 400
        data = response.json()
        # FastAPI wraps HTTPException detail in a 'detail' key
        detail = data if "error" in data else data.get("detail", {})
        assert "exceeds maximum length" in detail.get("error", "")

    def test_search_special_characters(self, test_client: TestClient, mock_kernel):
        """Test search with special characters in query."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=[])

        special_query = "<script>alert('test')</script>"
        response = test_client.get(f"/api/search?q={special_query}")

        # Should still work (input is sanitized)
        assert response.status_code in [200, 400]

    def test_search_plugin_error(self, test_client: TestClient, mock_kernel):
        """Test handling when book plugin raises an exception."""
        mock_kernel._plugins["book"].search = AsyncMock(
            side_effect=Exception("Search service unavailable")
        )

        response = test_client.get("/api/search?q=python")

        # Should return 502 for upstream service errors
        assert response.status_code == 502

    def test_search_unicode_query(self, test_client: TestClient, mock_kernel):
        """Test search with unicode characters."""
        mock_kernel._plugins["book"].search = AsyncMock(
            return_value=[{"id": "123", "title": "Python 编程", "authors": ["作者"]}]
        )

        response = test_client.get("/api/search?q=Python%20%E7%BC%96%E7%A8%8B")

        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["title"] == "Python 编程"


@pytest.mark.integration
class TestBookInfo:
    """Tests for GET /api/book/{book_id} endpoint."""

    def test_get_book_info_valid_id(self, test_client: TestClient, mock_kernel, sample_book_data):
        """Test retrieving book info with a valid ID."""
        mock_kernel._plugins["book"].fetch = AsyncMock(return_value=sample_book_data)

        response = test_client.get("/api/book/9780134685991")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "9780134685991"
        assert data["title"] == "Effective Python"
        assert data["isbn"] == "9780134685991"

    def test_get_book_info_not_found(self, test_client: TestClient, mock_kernel):
        """Test retrieving book info for non-existent book."""
        mock_kernel._plugins["book"].fetch = AsyncMock(side_effect=LookupError("Book not found"))

        response = test_client.get("/api/book/invalid-id-12345")

        assert response.status_code == 404
        data = response.json()
        detail = data if "error" in data else data.get("detail", {})
        assert "not found" in detail.get("error", "").lower()

    def test_get_book_info_invalid_id_format(self, test_client: TestClient, mock_kernel):
        """Test retrieving book info with invalid ID format."""
        mock_kernel._plugins["book"].fetch = AsyncMock(
            side_effect=ValueError("Invalid book ID format")
        )

        response = test_client.get("/api/book/not-a-valid-id!!!")

        assert response.status_code == 404

    def test_get_book_info_plugin_error(self, test_client: TestClient, mock_kernel):
        """Test handling when book plugin raises an unexpected error."""
        mock_kernel._plugins["book"].fetch = AsyncMock(side_effect=Exception("Unexpected error"))

        response = test_client.get("/api/book/9780134685991")

        assert response.status_code == 500
        data = response.json()
        detail = data if "error" in data else data.get("detail", {})
        assert "Unexpected error" in detail.get("error", "")

    def test_get_book_info_missing_optional_fields(self, test_client: TestClient, mock_kernel):
        """Test retrieving book with minimal data."""
        minimal_book = {
            "id": "12345",
            "title": "Minimal Book",
            # Missing many optional fields
        }
        mock_kernel._plugins["book"].fetch = AsyncMock(return_value=minimal_book)

        response = test_client.get("/api/book/12345")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "12345"
        assert data["title"] == "Minimal Book"


@pytest.mark.integration
class TestBookChapters:
    """Tests for GET /api/book/{book_id}/chapters endpoint."""

    def test_get_chapters_valid_book(
        self, test_client: TestClient, mock_kernel, sample_chapters_data
    ):
        """Test retrieving chapters for a valid book."""
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=sample_chapters_data)

        response = test_client.get("/api/book/9780134685991/chapters")

        assert response.status_code == 200
        data = response.json()
        assert "chapters" in data
        assert data["total"] == 5
        assert len(data["chapters"]) == 5

        # Check first chapter structure
        first_chapter = data["chapters"][0]
        assert first_chapter["index"] == 0
        assert first_chapter["title"] == "Introduction"
        assert first_chapter["pages"] == 10
        assert first_chapter["minutes"] == 15

    def test_get_chapters_book_not_found(self, test_client: TestClient, mock_kernel):
        """Test retrieving chapters for non-existent book."""
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(
            side_effect=LookupError("Book not found")
        )

        response = test_client.get("/api/book/invalid-id/chapters")

        assert response.status_code == 400
        data = response.json()
        detail = data if "error" in data else data.get("detail", {})
        assert "Book not found" in detail.get("error", "")

    def test_get_chapters_empty_chapters(self, test_client: TestClient, mock_kernel):
        """Test retrieving chapters when book has no chapters."""
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=[])

        response = test_client.get("/api/book/9780134685991/chapters")

        assert response.status_code == 200
        data = response.json()
        assert data["chapters"] == []
        assert data["total"] == 0

    def test_get_chapters_invalid_data_format(self, test_client: TestClient, mock_kernel):
        """Test handling when chapter data has invalid format."""
        invalid_chapters = [
            {
                "index": "not-a-number",
                "title": "Invalid Chapter",
            },  # index should be int
        ]
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=invalid_chapters)

        response = test_client.get("/api/book/9780134685991/chapters")

        # Should handle gracefully, either by converting or returning error
        assert response.status_code in [200, 502]

    def test_get_chapters_negative_values(self, test_client: TestClient, mock_kernel):
        """Test handling chapters with negative page/minute values."""
        chapters_with_negative = [
            {
                "index": 0,
                "title": "Chapter 1",
                "virtual_pages": -5,
                "minutes_required": -10,
            },
        ]
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=chapters_with_negative)

        response = test_client.get("/api/book/9780134685991/chapters")

        # Should handle gracefully - negative values should be converted to None
        assert response.status_code == 200
        data = response.json()
        chapter = data["chapters"][0]
        # Negative values should be normalized to None
        assert chapter.get("pages") is None
        assert chapter.get("minutes") is None

    def test_get_chapters_missing_optional_fields(self, test_client: TestClient, mock_kernel):
        """Test chapters with missing optional fields."""
        chapters_minimal = [
            {"index": 0, "title": "Chapter 1"},  # Missing pages and minutes
        ]
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=chapters_minimal)

        response = test_client.get("/api/book/9780134685991/chapters")

        assert response.status_code == 200
        data = response.json()
        chapter = data["chapters"][0]
        assert chapter["index"] == 0
        assert chapter["title"] == "Chapter 1"
        assert chapter.get("pages") is None
        assert chapter.get("minutes") is None

    def test_get_chapters_plugin_error(self, test_client: TestClient, mock_kernel):
        """Test handling when chapters plugin raises an error."""
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(
            side_effect=Exception("Chapters service error")
        )

        response = test_client.get("/api/book/9780134685991/chapters")

        assert response.status_code == 500
        data = response.json()
        detail = data if "error" in data else data.get("detail", {})
        assert "Unexpected error" in detail.get("error", "")


@pytest.mark.integration
class TestBookEndpointsCombined:
    """Tests combining multiple book-related endpoints."""

    def test_search_then_get_info(
        self,
        test_client: TestClient,
        mock_kernel,
        sample_search_results,
        sample_book_data,
    ):
        """Test search flow: search for book then get its details."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=sample_search_results)
        mock_kernel._plugins["book"].fetch = AsyncMock(return_value=sample_book_data)

        # Step 1: Search
        search_response = test_client.get("/api/search?q=python")
        assert search_response.status_code == 200
        books = search_response.json()["results"]
        book_id = books[0]["id"]

        # Step 2: Get book info
        info_response = test_client.get(f"/api/book/{book_id}")
        assert info_response.status_code == 200
        book_info = info_response.json()
        assert book_info["id"] == book_id

    def test_full_book_workflow(
        self,
        test_client: TestClient,
        mock_kernel,
        sample_search_results,
        sample_book_data,
        sample_chapters_data,
    ):
        """Test complete workflow: search -> info -> chapters."""
        mock_kernel._plugins["book"].search = AsyncMock(return_value=sample_search_results)
        mock_kernel._plugins["book"].fetch = AsyncMock(return_value=sample_book_data)
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=sample_chapters_data)

        # Search
        search_response = test_client.get("/api/search?q=effective%20python")
        assert search_response.status_code == 200

        # Get info
        book_id = sample_book_data["id"]
        info_response = test_client.get(f"/api/book/{book_id}")
        assert info_response.status_code == 200

        # Get chapters
        chapters_response = test_client.get(f"/api/book/{book_id}/chapters")
        assert chapters_response.status_code == 200
        chapters_data = chapters_response.json()
        assert chapters_data["total"] > 0


@pytest.mark.integration
class TestBookAPIEdgeCases:
    """Edge cases and boundary tests for book endpoints."""

    def test_book_id_with_special_characters(self, test_client: TestClient, mock_kernel):
        """Test book ID with special URL characters."""
        mock_kernel._plugins["book"].fetch = AsyncMock(
            return_value={"id": "book%20with%20spaces", "title": "Test Book"}
        )

        # URL-encoded book ID
        response = test_client.get("/api/book/book%20with%20spaces")

        assert response.status_code in [200, 400, 404]

    def test_very_long_book_id(self, test_client: TestClient, mock_kernel):
        """Test with extremely long book ID."""
        long_id = "a" * 500
        mock_kernel._plugins["book"].fetch = AsyncMock(side_effect=LookupError("Book not found"))

        response = test_client.get(f"/api/book/{long_id}")

        assert response.status_code in [400, 404, 414]  # 414 = URI Too Long

    def test_chapters_with_zero_pages(self, test_client: TestClient, mock_kernel):
        """Test handling chapters with zero pages."""
        chapters = [
            {"index": 0, "title": "Chapter", "virtual_pages": 0, "minutes_required": 0},
        ]
        mock_kernel._plugins["chapters"].fetch_list = AsyncMock(return_value=chapters)

        response = test_client.get("/api/book/123/chapters")

        assert response.status_code == 200
        data = response.json()
        # Zero pages should be normalized to None
        assert data["chapters"][0].get("pages") is None
