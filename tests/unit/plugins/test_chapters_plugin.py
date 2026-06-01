from __future__ import annotations

from types import SimpleNamespace

import pytest

import config
from plugins.chapters import ChaptersPlugin

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_chapters_fetch_list_breaks_repeated_pagination_next():
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
                        "content_url": "https://learning.oreilly.com/intro",
                        "related_assets": {"images": [], "stylesheets": []},
                        "virtual_pages": 1,
                        "minutes_required": 1.0,
                    }
                ],
                "next": first_url,
            }

    plugin = ChaptersPlugin()
    plugin.kernel = SimpleNamespace(http=DummyHttp())
    chapters = await plugin.fetch_list("demo")

    assert len(chapters) == 1
    assert calls["count"] == 1


def test_sanitize_remote_url_blocks_external_hosts():
    plugin = ChaptersPlugin()

    assert plugin._sanitize_remote_url("https://example.com/chapter.xhtml") == ""


def test_sanitize_remote_url_allows_base_host_and_subdomains():
    plugin = ChaptersPlugin()

    assert plugin._sanitize_remote_url("https://learning.oreilly.com/chapter.xhtml")
    assert plugin._sanitize_remote_url("https://cdn.learning.oreilly.com/chapter.xhtml")
