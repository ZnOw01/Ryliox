from __future__ import annotations

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from plugins.book import BookPlugin

pytestmark = pytest.mark.unit


def test_book_search_query_is_encoded():
    captured: dict[str, str | None] = {"url": None}

    class DummyHttp:
        async def get_json(self, url: str, **_kwargs):
            captured["url"] = url
            return {"results": []}

    plugin = BookPlugin()
    plugin.kernel = SimpleNamespace(http=DummyHttp())
    asyncio.run(plugin.search("python clean code", limit=10))

    assert captured["url"] is not None
    parsed = urlparse(captured["url"])
    params = parse_qs(parsed.query)
    assert params.get("query") == ["python clean code"]
