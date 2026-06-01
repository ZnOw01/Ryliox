from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from plugins.book import BookPlugin

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_book_search_query_is_encoded():
    captured: list[str] = []

    class DummyHttp:
        async def get_json(self, url: str, **_kwargs):
            captured.append(url)
            return {"results": []}

    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=DummyHttp())
    await plugin.search("python clean code", limit=10)

    search_urls = [url for url in captured if "/search/?" in url]
    assert search_urls
    parsed = urlparse(search_urls[0])
    params = parse_qs(parsed.query)
    assert params.get("query") == ["python clean code"]


@pytest.mark.asyncio
async def test_book_search_returns_results_from_api():
    """Test that search returns parsed results from the API."""
    plugin = BookPlugin()

    async def fake_get_json(url: str, **_kwargs):
        return {
            "results": [
                {
                    "archive_id": "9781098181642",
                    "title": "Aprender Java, 6a Edicion",
                    "authors": ["Marc Loy"],
                    "publishers": ["O'Reilly"],
                    "cover_url": "https://example.test/cover.png",
                    "content_format": "book",
                }
            ]
        }

    plugin.kernel = SimpleNamespace(http=SimpleNamespace(get_json=fake_get_json))

    results = await plugin.search("9781098181642")

    assert results == [
        {
            "id": "9781098181642",
            "title": "Aprender Java, 6a Edicion",
            "authors": ["Marc Loy"],
            "cover_url": "https://example.test/cover.png",
            "publishers": ["O'Reilly"],
        }
    ]


@pytest.mark.asyncio
async def test_book_search_returns_empty_list_for_no_results():
    """Test that search returns empty list when API returns no results."""
    plugin = BookPlugin()

    async def fake_get_json(_url: str, **_kwargs):
        # Return empty results from API
        return {"results": []}

    plugin.kernel = SimpleNamespace(http=SimpleNamespace(get_json=fake_get_json))

    # Use a fresh plugin instance to avoid cache issues
    fresh_plugin = BookPlugin()
    fresh_plugin.kernel = plugin.kernel

    results = await fresh_plugin.search("nonexistent-book-query")

    assert results == []


@pytest.mark.asyncio
async def test_fetch_enriches_sparse_metadata_from_epub_files(monkeypatch):
    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=SimpleNamespace())

    async def fake_fetch_search(_book_id: str):
        return {}

    async def fake_fetch_epub(_book_id: str):
        return {
            "ourn": "urn:orm:book:9781098181642",
            "title": "Aprender Java, 6a Edicion",
            "descriptions": {"text/html": "<p>desc</p>"},
            "isbn": "9781098181642",
            "language": "es",
            "publication_date": "2024-09-23",
            "virtual_pages": 865,
            "chapters": "chapters-url",
            "table_of_contents": "toc-url",
            "spine": "spine-url",
            "files": "files-url",
        }

    async def fake_fetch_epub_file(_book_id: str, relative_path: str):
        if relative_path == "titlepage01.html":
            return '<p class="author">Marc Loy, Patrick Niemeyer y Daniel Leuck</p>'
        if relative_path == "copyright-page01.html":
            return '<p class="publisher">Publicado por <span class="publishername">O\'Reilly Media, Inc.</span></p>'
        if relative_path == "cover.html":
            return '<figure data-type="cover"><img src="/api/v2/epubs/urn:orm:book:9781098181642/files/assets/cover.png"></figure>'
        return ""

    monkeypatch.setattr(plugin, "_fetch_search", fake_fetch_search)
    monkeypatch.setattr(plugin, "_fetch_epub", fake_fetch_epub)
    monkeypatch.setattr(plugin, "_fetch_epub_file", fake_fetch_epub_file)

    result = await plugin.fetch("9781098181642")

    assert result["authors"] == ["Marc Loy", "Patrick Niemeyer", "Daniel Leuck"]
    assert result["publishers"] == ["O'Reilly Media, Inc."]
    assert (
        result["cover_url"]
        == "https://learning.oreilly.com/api/v2/epubs/urn:orm:book:9781098181642/files/assets/cover.png"
    )


@pytest.mark.asyncio
async def test_fetch_uses_search_results_when_available(monkeypatch):
    """Test that fetch uses search results for metadata when available."""
    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=SimpleNamespace())

    # Use a different book_id to avoid cache conflicts with other tests
    test_book_id = "9780134685991"  # Different ID

    async def fake_fetch_search(_book_id: str):
        # Search provides complete metadata
        return {
            "authors": ["Brett Slatkin"],
            "publishers": ["Addison-Wesley"],
            "cover_url": "https://example.test/cover.png",
        }

    async def fake_fetch_epub(_book_id: str):
        # EPUB metadata is available
        return {
            "ourn": f"urn:orm:book:{test_book_id}",
            "title": "Effective Python",
            "descriptions": {"text/html": "<p>desc</p>"},
            "isbn": test_book_id,
            "language": "en",
        }

    async def fake_fetch_epub_file(_book_id: str, relative_path: str):
        # Fallback EPUB files should not be fetched since search has all metadata
        return ""

    monkeypatch.setattr(plugin, "_fetch_search", fake_fetch_search)
    monkeypatch.setattr(plugin, "_fetch_epub", fake_fetch_epub)
    monkeypatch.setattr(plugin, "_fetch_epub_file", fake_fetch_epub_file)

    result = await plugin.fetch(test_book_id)

    # Search results are used
    assert result["authors"] == ["Brett Slatkin"]
    assert result["publishers"] == ["Addison-Wesley"]
    assert result["cover_url"] == "https://example.test/cover.png"


@pytest.mark.asyncio
async def test_book_search_does_not_return_non_books():
    """Test that search filters out non-book content."""
    plugin = BookPlugin()

    async def fake_get_json(_url: str, **_kwargs):
        return {
            "results": [
                {
                    "archive_id": "video123",
                    "title": "Some Video Course",
                    "authors": ["Instructor"],
                    "content_format": "video",  # Not a book
                },
                {
                    "archive_id": "book456",
                    "title": "A Real Book",
                    "authors": ["Author"],
                    "content_format": "book",
                },
            ]
        }

    plugin.kernel = SimpleNamespace(http=SimpleNamespace(get_json=fake_get_json))

    results = await plugin.search("test")

    # Should only return the book, not the video
    assert len(results) == 1
    assert results[0]["id"] == "book456"
    assert results[0]["title"] == "A Real Book"
