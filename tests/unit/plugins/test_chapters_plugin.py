from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import config
from plugins.chapters import ChaptersPlugin

pytestmark = pytest.mark.unit


def test_chapters_fetch_list_breaks_repeated_pagination_next():
    first_url = f"{config.API_V2}/epub-chapters/?epub_identifier=urn:orm:book:demo"
    calls: dict[str, int] = {"count": 0}

    class DummyHttp:
        async def get_json(self, url: str, **_kwargs):
            calls["count"] += 1
            assert url == first_url
            return {
                "results": [
                    {
                        "ourn": "urn:orm:chapter:1",
                        "title": "Intro",
                        "reference_id": "book-/intro.xhtml",
                        "content_url": "https://example.com/intro",
                        "related_assets": {"images": [], "stylesheets": []},
                        "virtual_pages": 1,
                        "minutes_required": 1.0,
                    }
                ],
                "next": first_url,
            }

    plugin = ChaptersPlugin()
    plugin.kernel = SimpleNamespace(http=DummyHttp())
    chapters = asyncio.run(plugin.fetch_list("demo"))

    assert len(chapters) == 1
    assert calls["count"] == 1
