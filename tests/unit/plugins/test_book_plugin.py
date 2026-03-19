from __future__ import annotations

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from plugins.book import BookPlugin

pytestmark = pytest.mark.unit


def test_book_search_query_is_encoded():
    captured: list[str] = []

    class DummyHttp:
        async def get_json(self, url: str, **_kwargs):
            captured.append(url)
            return {"results": []}

    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=DummyHttp())
    asyncio.run(plugin.search("python clean code", limit=10))

    search_urls = [url for url in captured if "/search/?" in url]
    assert search_urls
    parsed = urlparse(search_urls[0])
    params = parse_qs(parsed.query)
    assert params.get("query") == ["python clean code"]


def test_book_search_falls_back_to_direct_fetch_for_archive_id(monkeypatch):
    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=SimpleNamespace())

    async def fake_get_json(url: str, **_kwargs):
        assert "query=9781098181642" in url
        return {"results": []}

    async def fake_fetch(book_id: str):
        assert book_id == "9781098181642"
        return {
            "id": book_id,
            "title": "Aprender Java, 6a Edicion",
            "authors": [],
            "publishers": [],
            "cover_url": None,
        }

    plugin.http.get_json = fake_get_json  # type: ignore[method-assign]
    monkeypatch.setattr(plugin, "fetch", fake_fetch)

    results = asyncio.run(plugin.search("9781098181642"))

    assert results == [
        {
            "id": "9781098181642",
            "title": "Aprender Java, 6a Edicion",
            "authors": [],
            "cover_url": None,
            "publishers": [],
        }
    ]


def test_book_search_falls_back_when_query_is_oreilly_url(monkeypatch):
    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=SimpleNamespace())

    async def fake_get_json(_url: str, **_kwargs):
        return {"results": []}

    async def fake_fetch(book_id: str):
        assert book_id == "9781098181642"
        return {
            "id": book_id,
            "title": "Aprender Java, 6a Edicion",
            "authors": ["Marc Loy"],
            "publishers": ["O'Reilly"],
            "cover_url": None,
        }

    plugin.http.get_json = fake_get_json  # type: ignore[method-assign]
    monkeypatch.setattr(plugin, "fetch", fake_fetch)

    results = asyncio.run(
        plugin.search("https://learning.oreilly.com/library/view/aprender-java-6a/9781098181642/")
    )

    assert results[0]["id"] == "9781098181642"


def test_fetch_enriches_sparse_metadata_from_epub_files(monkeypatch):
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

    result = asyncio.run(plugin.fetch("9781098181642"))

    assert result["authors"] == ["Marc Loy", "Patrick Niemeyer", "Daniel Leuck"]
    assert result["publishers"] == ["O'Reilly Media, Inc."]
    assert result["cover_url"] == "https://learning.oreilly.com/api/v2/epubs/urn:orm:book:9781098181642/files/assets/cover.png"
